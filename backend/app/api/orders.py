import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_cashier_or_above, require_staff, require_kitchen_or_above, require_manager_or_admin
from app.core.inventory import deduct_inventory_for_order, reverse_inventory_for_order
from app.db.session import get_db
from app.models.menu_item import MenuItem
from app.models.order import Order, OrderItem
from app.models.table import RestaurantTable
from app.models.user import User
from app.schemas.order import (
    DEFAULT_TAX_RATE,
    OrderCreate,
    OrderItemResponse,
    OrderResponse,
    OrderUpdate,
)

router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"],
)

# ── Helper functions ─────────────────────────────────────────────────────

ACTIVE_ORDER_STATUSES = ("pending", "in_progress", "served")
TERMINAL_STATUSES = ("completed", "cancelled")

# Permitted state machine transitions for orders
ALLOWED_TRANSITIONS_DINE_IN = {
    "pending": {"in_progress", "cancelled"},
    "in_progress": {"served", "cancelled"},
    "served": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

ALLOWED_TRANSITIONS_TAKEAWAY = {
    "pending": {"in_progress", "completed", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "served": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def _generate_order_number() -> str:
    """Generate a unique order number: ORD-YYYYMMDD-<short uuid>."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:6].upper()
    return f"ORD-{today}-{short_id}"


def _quantize(value: Decimal) -> Decimal:
    """Round a Decimal to 2 decimal places using half-up rounding."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _build_order_response(order: Order) -> dict:
    """Build a response dict from an Order ORM object with nested item details."""
    items = []
    for oi in order.order_items:
        item_dict = {
            "id": oi.id,
            "order_id": oi.order_id,
            "menu_item_id": oi.menu_item_id,
            "quantity": oi.quantity,
            "unit_price": oi.unit_price,
            "special_instructions": oi.special_instructions,
            "menu_item_name": oi.menu_item.name if oi.menu_item else None,
            "created_at": oi.created_at,
            "updated_at": oi.updated_at,
        }
        items.append(item_dict)

    return {
        "id": order.id,
        "order_number": order.order_number,
        "table_id": order.table_id,
        "table_number": order.table.table_number if order.table else None,
        "status": order.status,
        "subtotal": order.subtotal,
        "tax": order.tax,
        "discount": order.discount,
        "total": order.total,
        "items": items,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "completed_at": order.completed_at,
        "inventory_deducted": getattr(order, "inventory_deducted", False),
    }


# ── POST /api/orders ─────────────────────────────────────────────────────

@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order with items",
)
def create_order(
    order_in: OrderCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_cashier_or_above),
):
    """Create a new order with one or more items in a single transaction.

    - Validates table existence and checks for conflicting active orders at the table.
    - Validates menu item existence and availability.
    - Snapshots unit prices from the current menu prices (never trusts client prices).
    - Calculates subtotal, tax (default 0%), and total server-side.
    - Validates discount does not exceed subtotal + tax.
    - Generates a unique order number.
    - Rolls back fully on any failure.
    """
    # 1. Validate table if provided (acquire row-level lock to prevent concurrent double-booking)
    table = None
    if order_in.table_id is not None:
        table = (
            db.query(RestaurantTable)
            .filter(RestaurantTable.id == order_in.table_id)
            .with_for_update()
            .first()
        )
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table with ID {order_in.table_id} not found.",
            )
        # Check if table already has an active order
        existing_active = (
            db.query(Order)
            .filter(
                Order.table_id == order_in.table_id,
                Order.status.in_(ACTIVE_ORDER_STATUSES),
            )
            .first()
        )
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Table '{table.table_number}' already has an active order "
                    f"(#{existing_active.order_number}, status: {existing_active.status}). "
                    f"Complete or cancel it before placing a new order."
                ),
            )

    # 2. Validate and collect menu items
    menu_item_ids = [item.menu_item_id for item in order_in.items]
    menu_items_db = db.query(MenuItem).filter(MenuItem.id.in_(menu_item_ids)).all()
    menu_items_map = {mi.id: mi for mi in menu_items_db}

    for item_in in order_in.items:
        mi = menu_items_map.get(item_in.menu_item_id)
        if not mi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Menu item with ID {item_in.menu_item_id} not found.",
            )
        if not mi.is_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Menu item '{mi.name}' (ID {mi.id}) is currently unavailable.",
            )

    # 3. Calculate financial totals server-side
    subtotal = Decimal("0.00")
    order_items_to_create = []
    for item_in in order_in.items:
        mi = menu_items_map[item_in.menu_item_id]
        snapshot_price = _quantize(mi.price)
        line_total = _quantize(Decimal(item_in.quantity) * snapshot_price)
        subtotal += line_total
        order_items_to_create.append((item_in, snapshot_price))

    subtotal = _quantize(subtotal)
    tax = _quantize(subtotal * DEFAULT_TAX_RATE)
    discount = _quantize(order_in.discount)

    # 4. Validate discount constraint: discount <= subtotal + tax
    if discount > (subtotal + tax):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Discount ({discount}) cannot exceed subtotal + tax ({subtotal + tax})."
            ),
        )

    total = _quantize(subtotal + tax - discount)
    if total < Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Calculated total cannot be negative.",
        )

    # 5. Generate unique order number with collision retry
    order_number = _generate_order_number()
    for _ in range(5):
        exists = db.query(Order).filter(Order.order_number == order_number).first()
        if not exists:
            break
        order_number = _generate_order_number()

    # 6. Create order + items in a single transaction
    new_order = Order(
        order_number=order_number,
        table_id=order_in.table_id,
        status="pending",
        subtotal=subtotal,
        tax=tax,
        discount=discount,
        total=total,
    )
    db.add(new_order)

    try:
        db.flush()  # Get the new_order.id without committing

        for item_in, snapshot_price in order_items_to_create:
            oi = OrderItem(
                order_id=new_order.id,
                menu_item_id=item_in.menu_item_id,
                quantity=item_in.quantity,
                unit_price=snapshot_price,
                special_instructions=item_in.special_instructions,
            )
            db.add(oi)

        # Mark table as occupied if dine-in
        if table is not None:
            table.status = "occupied"

        db.commit()
        db.refresh(new_order)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order could not be created due to a database conflict (e.g., duplicate order number).",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while creating the order.",
        )

    # 7. Reload with relationships for the response
    order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.table),
        )
        .filter(Order.id == new_order.id)
        .first()
    )

    return _build_order_response(order)


# ── GET /api/orders ───────────────────────────────────────────────────────

@router.get(
    "",
    response_model=List[OrderResponse],
    status_code=status.HTTP_200_OK,
    summary="List orders",
)
def list_orders(
    order_status: Optional[str] = Query(None, alias="status", description="Filter by order status"),
    table_id: Optional[int] = Query(None, description="Filter by table ID"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve all orders with items and table info. Supports status and table_id filters."""
    query = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.table),
        )
    )

    if order_status is not None:
        query = query.filter(Order.status == order_status)
    if table_id is not None:
        query = query.filter(Order.table_id == table_id)

    orders = query.order_by(Order.id.asc()).all()
    # Deduplicate due to joinedload producing duplicates
    seen = set()
    unique_orders = []
    for o in orders:
        if o.id not in seen:
            seen.add(o.id)
            unique_orders.append(o)

    return [_build_order_response(o) for o in unique_orders]


# ── GET /api/orders/{order_id} ────────────────────────────────────────────

@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get order by ID",
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve a single order with its items and table details."""
    order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.table),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found.",
        )
    return _build_order_response(order)


# ── PUT /api/orders/{order_id} ────────────────────────────────────────────

@router.put(
    "/{order_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an order",
)
def update_order(
    order_id: int,
    order_in: OrderUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Update order status, discount, or table assignment.

    Business rules:
    - Cannot modify a completed or cancelled order.
    - Setting status to 'completed' or 'cancelled' sets completed_at and frees the table.
    - Transitioning away from a terminal status is not allowed.
    - Discount must not exceed subtotal + tax; total must remain non-negative.
    - Table reassignment validates the new table exists and has no conflicting active order.
    """
    order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.table),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found.",
        )

    # Block changes to terminal orders
    if order.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order '{order.order_number}' is already '{order.status}' and cannot be modified.",
        )

    # Kitchen role restrictions: cannot reassign tables, modify discounts, or finalize billing
    if _user.role == "kitchen":
        if "table_id" in order_in.model_fields_set or order_in.discount is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Kitchen staff are only permitted to update order preparation status, not table assignments or discounts.",
            )
        if order_in.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Kitchen staff cannot finalize and complete order billing. Cashier or Manager required.",
            )

    # ── Handle table_id reassignment ──
    if "table_id" in order_in.model_fields_set:
        target_table_id = order_in.table_id
        if target_table_id != order.table_id:
            if target_table_id is not None:
                new_table = (
                    db.query(RestaurantTable)
                    .filter(RestaurantTable.id == target_table_id)
                    .with_for_update()
                    .first()
                )
                if not new_table:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Table with ID {target_table_id} not found.",
                    )
                # Check for active order at the new table (excluding this order)
                conflict_order = (
                    db.query(Order)
                    .filter(
                        Order.table_id == target_table_id,
                        Order.status.in_(ACTIVE_ORDER_STATUSES),
                        Order.id != order_id,
                    )
                    .first()
                )
                if conflict_order:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Table '{new_table.table_number}' already has an active order "
                            f"(#{conflict_order.order_number}). Complete or cancel it first."
                        ),
                    )
                # Free old table if it was occupied by this order
                if order.table_id is not None and order.table:
                    order.table.status = "available"
                # Assign and occupy new table
                order.table_id = target_table_id
                new_table.status = "occupied"
            else:
                # Converting dine-in order to takeaway: detach table and free it
                if order.table_id is not None and order.table:
                    order.table.status = "available"
                order.table_id = None

    # ── Handle discount update ──
    if order_in.discount is not None:
        discount = _quantize(order_in.discount)
        if discount > (order.subtotal + order.tax):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Discount ({discount}) cannot exceed subtotal + tax "
                    f"({order.subtotal + order.tax})."
                ),
            )
        order.discount = discount
        order.total = _quantize(order.subtotal + order.tax - discount)

    # ── Handle status update with state machine validation ──
    if order_in.status is not None:
        new_status = order_in.status
        if new_status != order.status:
            # Check state transition rules
            allowed = (
                ALLOWED_TRANSITIONS_DINE_IN.get(order.status, set())
                if order.table_id is not None
                else ALLOWED_TRANSITIONS_TAKEAWAY.get(order.status, set())
            )
            if new_status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Cannot transition order '{order.order_number}' from '{order.status}' to '{new_status}'. "
                        f"Allowed next statuses: {', '.join(sorted(allowed)) if allowed else 'none'}."
                    ),
                )

            if new_status in TERMINAL_STATUSES:
                # Set completion timestamp
                order.completed_at = datetime.now(timezone.utc)
                # Free the table ONLY if no other active orders remain for this table
                if order.table_id is not None:
                    tbl = db.query(RestaurantTable).filter(RestaurantTable.id == order.table_id).first()
                    if tbl:
                        remaining_active = (
                            db.query(Order)
                            .filter(
                                Order.table_id == order.table_id,
                                Order.id != order.id,
                                Order.status.in_(ACTIVE_ORDER_STATUSES),
                            )
                            .count()
                        )
                        if remaining_active == 0:
                            tbl.status = "available"

            # ── Inventory Integration: Deduct or Reverse based on status transition ──
            if new_status in ("in_progress", "completed") and not order.inventory_deducted:
                deduct_inventory_for_order(db, order, acting_user=_user)
            elif new_status == "cancelled" and order.inventory_deducted:
                reverse_inventory_for_order(db, order, acting_user=_user)

            order.status = new_status

    try:
        db.commit()
        db.refresh(order)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order update failed due to a database constraint violation.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while updating the order.",
        )

    # Reload with relationships
    order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.table),
        )
        .filter(Order.id == order_id)
        .first()
    )

    return _build_order_response(order)


# ── DELETE /api/orders/{order_id} ─────────────────────────────────────────

@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a pending order",
)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Delete an order only if it is still in 'pending' status.

    - Pending orders with no kitchen activity can be safely discarded.
    - Orders that have progressed beyond 'pending' must be cancelled instead,
      to preserve historical records for analytics and audit.
    - Cascade deletes order items (ON DELETE CASCADE in the schema).
    - Frees the associated table if one was assigned.
    - Returns 204 No Content with an empty body on success.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found.",
        )

    if order.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete order '{order.order_number}' because its status is '{order.status}'. "
                f"Only 'pending' orders can be deleted. Use PUT to cancel this order instead."
            ),
        )

    # Free the table ONLY if no other active orders remain for this table
    if order.table_id is not None:
        tbl = db.query(RestaurantTable).filter(RestaurantTable.id == order.table_id).first()
        if tbl:
            remaining_active = (
                db.query(Order)
                .filter(
                    Order.table_id == order.table_id,
                    Order.id != order.id,
                    Order.status.in_(ACTIVE_ORDER_STATUSES),
                )
                .count()
            )
            if remaining_active == 0:
                tbl.status = "available"

    # Reverse any inventory deducted if applicable
    if getattr(order, "inventory_deducted", False):
        reverse_inventory_for_order(db, order, acting_user=_user)

    try:
        db.delete(order)
        db.commit()
        return None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while deleting the order.",
        )
