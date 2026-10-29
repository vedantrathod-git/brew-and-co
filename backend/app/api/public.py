import hashlib
import json
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.api.orders import ACTIVE_ORDER_STATUSES, _generate_order_number, _quantize
from app.db.session import get_db
from app.models.category import Category
from app.models.menu_item import MenuItem
from app.models.order import Order, OrderItem
from app.models.table import RestaurantTable
from app.schemas.order import DEFAULT_TAX_RATE
from app.schemas.public_menu import (
    PublicCategoryResponse,
    PublicMenuItemResponse,
    PublicMenuResponse,
)
from app.schemas.qr_order import (
    QROrderCreate,
    QROrderItemResponse,
    QROrderResponse,
    QROrderStatusResponse,
    QRTableInfoResponse,
)

router = APIRouter(
    prefix="/api/public",
    tags=["Public Menu"],
)


@router.get(
    "/menu",
    response_model=PublicMenuResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer-facing public café menu",
)
def get_public_menu(
    category_id: Optional[int] = Query(None, description="Optional category ID filter"),
    search: Optional[str] = Query(None, description="Optional search term matching name or description"),
    db: Session = Depends(get_db),
):
    """Retrieve public café menu catalog without requiring authentication.

    - Returns ONLY available products (`is_available = True`).
    - Excludes retired legacy items.
    - Excludes empty legacy categories that have no active products.
    - Exposes customer-safe fields only (no internal audit timestamps or staff metadata).
    """
    # 1. Fetch categories that contain at least one available menu item
    category_counts = (
        db.query(
            Category.id,
            Category.name,
            Category.description,
            func.count(MenuItem.id).label("active_item_count"),
        )
        .join(MenuItem, MenuItem.category_id == Category.id)
        .filter(MenuItem.is_available == True)  # noqa: E712
        .group_by(Category.id, Category.name, Category.description)
        .order_by(Category.id.asc())
        .all()
    )

    public_categories = [
        PublicCategoryResponse(
            id=cat_id,
            name=name,
            description=description,
            item_count=count,
        )
        for cat_id, name, description, count in category_counts
    ]

    # 2. Query available menu items
    items_query = (
        db.query(MenuItem)
        .options(joinedload(MenuItem.category))
        .filter(MenuItem.is_available == True)  # noqa: E712
    )

    if category_id is not None:
        items_query = items_query.filter(MenuItem.category_id == category_id)

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        items_query = items_query.filter(
            func.lower(MenuItem.name).like(term)
            | func.lower(MenuItem.description).like(term)
        )

    items = items_query.order_by(MenuItem.category_id.asc(), MenuItem.id.asc()).all()

    public_items = [
        PublicMenuItemResponse(
            id=item.id,
            category_id=item.category_id,
            category_name=item.category.name if item.category else None,
            name=item.name,
            description=item.description,
            price=item.price,
            is_available=item.is_available,
            prep_time_minutes=item.prep_time_minutes,
        )
        for item in items
    ]

    return PublicMenuResponse(
        categories=public_categories,
        items=public_items,
        total_categories=len(public_categories),
        total_items=len(public_items),
    )


@router.get(
    "/categories",
    response_model=List[PublicCategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get active café categories",
)
def get_public_categories(
    db: Session = Depends(get_db),
):
    """Retrieve only categories that have at least one active, available menu item."""
    category_counts = (
        db.query(
            Category.id,
            Category.name,
            Category.description,
            func.count(MenuItem.id).label("active_item_count"),
        )
        .join(MenuItem, MenuItem.category_id == Category.id)
        .filter(MenuItem.is_available == True)  # noqa: E712
        .group_by(Category.id, Category.name, Category.description)
        .order_by(Category.id.asc())
        .all()
    )

    return [
        PublicCategoryResponse(
            id=cat_id,
            name=name,
            description=description,
            item_count=count,
        )
        for cat_id, name, description, count in category_counts
    ]


@router.get(
    "/menu-items",
    response_model=List[PublicMenuItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get available café menu items",
)
def get_public_menu_items(
    category_id: Optional[int] = Query(None, description="Filter items by category ID"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    db: Session = Depends(get_db),
):
    """Retrieve all active, available menu items with customer-safe fields."""
    query = (
        db.query(MenuItem)
        .options(joinedload(MenuItem.category))
        .filter(MenuItem.is_available == True)  # noqa: E712
    )

    if category_id is not None:
        query = query.filter(MenuItem.category_id == category_id)

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            func.lower(MenuItem.name).like(term)
            | func.lower(MenuItem.description).like(term)
        )

    items = query.order_by(MenuItem.category_id.asc(), MenuItem.id.asc()).all()

    return [
        PublicMenuItemResponse(
            id=item.id,
            category_id=item.category_id,
            category_name=item.category.name if item.category else None,
            name=item.name,
            description=item.description,
            price=item.price,
            is_available=item.is_available,
            prep_time_minutes=item.prep_time_minutes,
        )
        for item in items
    ]


# ── Customer QR Table Ordering Endpoints ─────────────────────────────────

def _compute_request_fingerprint(order_in: QROrderCreate) -> str:
    """Compute a deterministic SHA-256 fingerprint over the canonical order payload."""
    canonical_items = sorted(
        [
            {
                "id": it.menu_item_id,
                "qty": it.quantity,
                "notes": (it.special_instructions or "").strip(),
            }
            for it in order_in.items
        ],
        key=lambda x: (x["id"], x["notes"], x["qty"]),
    )
    payload_repr = json.dumps(
        {
            "qr_token": order_in.qr_token or "",
            "items": canonical_items,
            "customer_name": (order_in.customer_name or "").strip(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload_repr.encode("utf-8")).hexdigest()


def _build_qr_order_response(order: Order, table_number: str) -> QROrderResponse:
    items = []
    for oi in order.order_items:
        items.append(
            QROrderItemResponse(
                menu_item_name=oi.menu_item.name if oi.menu_item else f"Dish #{oi.menu_item_id}",
                quantity=oi.quantity,
                unit_price=oi.unit_price,
                special_instructions=oi.special_instructions,
            )
        )
    return QROrderResponse(
        order_number=order.order_number,
        table_number=table_number,
        status=order.status,
        payment_status=order.payment_status,
        payment_method=order.payment_method,
        items=items,
        subtotal=order.subtotal,
        tax=order.tax,
        total=order.total,
        created_at=order.created_at,
    )


@router.get(
    "/table/{qr_token}",
    response_model=QRTableInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate table QR token and retrieve table info",
)
def get_qr_table_info(
    qr_token: str,
    db: Session = Depends(get_db),
):
    """Validate a table QR code and return physical table details without requiring authentication.

    - Returns 404 if the token does not exist or has been revoked.
    - Reports whether the table currently has an active order session.
    """
    table = db.query(RestaurantTable).filter(RestaurantTable.qr_token == qr_token).first()
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or revoked QR code. Please scan a valid table QR code.",
        )

    active_order = (
        db.query(Order)
        .filter(
            Order.table_id == table.id,
            Order.status.in_(ACTIVE_ORDER_STATUSES),
        )
        .first()
    )

    return QRTableInfoResponse(
        table_number=table.table_number,
        capacity=table.capacity,
        has_active_order=active_order is not None,
    )


@router.post(
    "/orders",
    response_model=QROrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer dine-in order via table QR code",
)
def create_qr_order(
    order_in: QROrderCreate,
    db: Session = Depends(get_db),
):
    """Create a new dine-in order directly from a physical table QR code scan.

    Security & Safety Guarantees:
    - Validates QR token matches an existing physical table.
    - Request fingerprinting: computes SHA-256 hash of canonical order payload.
    - Idempotency guard: duplicate requests with matching `idempotency_key` and matching payload
      safely return the original order without creating another order.
    - Tamper rejection: reusing an existing `idempotency_key` with a different payload returns HTTP 409.
    - Concurrency protection: acquires a row-level lock (`with_for_update()`) on the table and handles
      concurrent unique constraint conflicts cleanly.
    - Multiple consecutive orders per table: seated guests can order additional rounds (e.g. drinks,
      desserts); table remains occupied and only clears when all orders reach terminal status.
    - Server-side price authority: snapshots unit prices directly from database; client prices are ignored.
    - Atomic transaction: order creation and table occupancy update happen in a single transaction.
      Validation failures roll back fully with zero partial changes.
    - Order is created in 'pending' status with inventory_deducted=False. Inventory deduction occurs
      only when staff advances the order to 'in_progress' or 'completed'.
    """
    # 1. Compute request fingerprint
    fingerprint = _compute_request_fingerprint(order_in)

    # 2. Idempotency Check: check if idempotency_key was already submitted
    existing_order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.table),
        )
        .filter(Order.idempotency_key == order_in.idempotency_key)
        .first()
    )
    if existing_order:
        if existing_order.request_fingerprint and existing_order.request_fingerprint != fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key has already been used with a different request payload.",
            )
        table_num = existing_order.table.table_number if existing_order.table else "Dine-In"
        return _build_qr_order_response(existing_order, table_num)

    # 3. Validate QR token and acquire row-level lock on physical table if dine-in
    table = None
    table_num = "Takeaway"
    if order_in.qr_token:
        table = (
            db.query(RestaurantTable)
            .filter(RestaurantTable.qr_token == order_in.qr_token)
            .with_for_update()
            .first()
        )
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The scanned QR code is invalid or has been deactivated.",
            )
        table_num = table.table_number

    # Note on Multiple Orders per Table:
    # Seated guests may place additional rounds from their table. We do NOT block subsequent
    # orders for an already occupied table, provided the QR token is valid.

    # 4. Validate menu items and check availability
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
                detail=f"Menu item '{mi.name}' is currently unavailable.",
            )

    # 5. Snapshot prices and calculate financials server-side
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
    total = _quantize(subtotal + tax)

    # 6. Generate unique order number with collision protection
    order_number = _generate_order_number()
    for _ in range(5):
        exists = db.query(Order).filter(Order.order_number == order_number).first()
        if not exists:
            break
        order_number = _generate_order_number()

    # 7. Atomic transaction: create Order + OrderItems, set table status to occupied if dine-in
    new_order = Order(
        order_number=order_number,
        table_id=table.id if table else None,
        status="pending",
        subtotal=subtotal,
        tax=tax,
        discount=Decimal("0.00"),
        total=total,
        idempotency_key=order_in.idempotency_key,
        request_fingerprint=fingerprint,
    )
    db.add(new_order)

    try:
        db.flush()
        for item_in, snapshot_price in order_items_to_create:
            oi = OrderItem(
                order_id=new_order.id,
                menu_item_id=item_in.menu_item_id,
                quantity=item_in.quantity,
                unit_price=snapshot_price,
                special_instructions=item_in.special_instructions,
            )
            db.add(oi)

        # Set table status to occupied within the atomic transaction if dine-in
        if table:
            table.status = "occupied"
        db.commit()
        db.refresh(new_order)
    except IntegrityError:
        db.rollback()
        # Handle concurrent submissions attempting the same idempotency key simultaneously
        winner_order = (
            db.query(Order)
            .options(
                joinedload(Order.order_items).joinedload(OrderItem.menu_item),
                joinedload(Order.table),
            )
            .filter(Order.idempotency_key == order_in.idempotency_key)
            .first()
        )
        if winner_order:
            if winner_order.request_fingerprint and winner_order.request_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key has already been used with a different request payload.",
                )
            table_num = winner_order.table.table_number if winner_order.table else "Dine-In"
            return _build_qr_order_response(winner_order, table_num)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order could not be placed due to a database constraint conflict. Please retry.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while creating your order.",
        )

    # Reload with items
    loaded_order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.table),
        )
        .filter(Order.id == new_order.id)
        .first()
    )
    return _build_qr_order_response(loaded_order, table_num)


@router.get(
    "/orders/{order_number}",
    response_model=QROrderStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check QR order live status",
)
def get_qr_order_status(
    order_number: str,
    qr_token: str = Query(..., description="Active table QR token for verification"),
    db: Session = Depends(get_db),
):
    """Retrieve the real-time fulfillment status of a QR table order.

    Strict Privacy Guarantees:
    - Validates that the provided `qr_token` matches the physical table of the order,
      preventing arbitrary order inspection.
    - Exposes customer-safe fields only (status, public totals, ordered dish names, instructions).
    - Omits internal primary keys, staff notes, and user account records.
    """
    order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.table),
        )
        .filter(Order.order_number == order_number)
        .first()
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_number}' not found.",
        )

    # Validate that this order belongs to the table associated with qr_token
    if not order.table or order.table.qr_token != qr_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. The provided QR token does not match this order's table.",
        )

    items = [
        QROrderItemResponse(
            menu_item_name=oi.menu_item.name if oi.menu_item else f"Dish #{oi.menu_item_id}",
            quantity=oi.quantity,
            unit_price=oi.unit_price,
            special_instructions=oi.special_instructions,
        )
        for oi in order.order_items
    ]

    return QROrderStatusResponse(
        order_number=order.order_number,
        table_number=order.table.table_number,
        status=order.status,
        payment_status=order.payment_status,
        payment_method=order.payment_method,
        total=order.total,
        created_at=order.created_at,
        items=items,
    )
