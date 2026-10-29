import secrets
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import require_manager_or_admin, require_staff
from app.db.session import get_db
from app.models.order import Order
from app.models.table import RestaurantTable
from app.models.user import User
from app.schemas.qr_order import QRTokenResponse
from app.schemas.table import TableCreate, TableResponse, TableUpdate

router = APIRouter(
    prefix="/api/tables",
    tags=["Restaurant Tables"],
)


@router.post(
    "",
    response_model=TableResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new restaurant table",
)
def create_table(
    table_in: TableCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Create a new restaurant table.

    - Checks that the table number is unique (case-insensitive, returns 409 if duplicate).
    - Returns 201 Created on success.
    """
    # Proactive case-insensitive duplicate check
    existing = db.query(RestaurantTable).filter(
        func.lower(RestaurantTable.table_number) == table_in.table_number.lower()
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Table with number '{table_in.table_number}' already exists.",
        )

    new_table = RestaurantTable(
        table_number=table_in.table_number,
        capacity=table_in.capacity,
        status=table_in.status,
    )
    db.add(new_table)
    try:
        db.commit()
        db.refresh(new_table)
        return new_table
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Table with number '{table_in.table_number}' already exists.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while creating the table.",
        )


@router.get(
    "",
    response_model=List[TableResponse],
    status_code=status.HTTP_200_OK,
    summary="List all restaurant tables",
)
def list_tables(
    status: Optional[str] = Query(
        None,
        description="Filter tables by status: 'available', 'occupied', or 'reserved'",
    ),
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve all restaurant tables ordered by ID, with optional status filter."""
    query = db.query(RestaurantTable)
    if status is not None:
        query = query.filter(RestaurantTable.status == status)

    tables = query.order_by(RestaurantTable.id.asc()).all()
    return tables


@router.get(
    "/{table_id}",
    response_model=TableResponse,
    status_code=status.HTTP_200_OK,
    summary="Get table by ID",
)
def get_table(
    table_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve a single table by its primary key ID.

    Returns 404 if the table does not exist.
    """
    table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID {table_id} not found.",
        )
    return table


@router.put(
    "/{table_id}",
    response_model=TableResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a table",
)
def update_table(
    table_id: int,
    table_in: TableUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Update a table's number, capacity, and status.

    - Validates that the table exists (404).
    - Checks for table number collisions with other tables (409).
    - Returns 200 OK with the updated table.
    """
    table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID {table_id} not found.",
        )

    # Check for name collision with another table (case-insensitive)
    conflict = db.query(RestaurantTable).filter(
        func.lower(RestaurantTable.table_number) == table_in.table_number.lower(),
        RestaurantTable.id != table_id,
    ).first()
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another table with number '{table_in.table_number}' already exists.",
        )

    table.table_number = table_in.table_number
    table.capacity = table_in.capacity
    table.status = table_in.status

    try:
        db.commit()
        db.refresh(table)
        return table
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another table with number '{table_in.table_number}' already exists.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while updating the table.",
        )


@router.delete(
    "/{table_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a table",
)
def delete_table(
    table_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Delete a table by ID.

    - Returns 204 No Content with an empty body on success.
    - Returns 404 if the table does not exist.
    - Returns 409 Conflict if the table is currently occupied or has active in-progress orders.
    - If historical completed/cancelled orders reference this table, PostgreSQL's ON DELETE SET NULL
      foreign key rule cleanly detaches the table reference (orders.table_id = NULL) without deleting
      any orders or historical order items.
    """
    table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID {table_id} not found.",
        )

    # 1. Conflict check: do not delete if marked occupied
    if table.status == "occupied":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete table '{table.table_number}' because it is currently marked as occupied. "
                f"Please clear the table before deleting."
            ),
        )

    # 2. Conflict check: do not delete if active in-progress orders exist at this table
    active_orders_count = (
        db.query(Order)
        .filter(
            Order.table_id == table_id,
            Order.status.in_(["pending", "in_progress", "served"]),
        )
        .count()
    )
    if active_orders_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete table '{table.table_number}' because {active_orders_count} "
                f"active order(s) are currently seated at it. Please complete or cancel those orders first."
            ),
        )

    try:
        db.delete(table)
        db.commit()
        return None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete table '{table.table_number}' due to database constraints.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while deleting the table.",
        )


# ── Staff QR Table Identity Endpoints ─────────────────────────────────────

@router.post(
    "/{table_id}/qr-token",
    response_model=QRTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate or rotate table QR ordering token",
)
def generate_table_qr_token(
    table_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Generate or rotate a secure, cryptographically random QR ordering token for a table.

    - Token is URL-safe and unguessable (32 bytes entropy).
    - Invalidates any prior token for this table immediately.
    - Requires Manager or Admin role.
    """
    table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID {table_id} not found.",
        )

    new_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    table.qr_token = new_token
    table.qr_token_created_at = now

    try:
        db.commit()
        db.refresh(table)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist generated QR token.",
        )

    # Base URL pointing to the customer web app order route
    base_url = "http://localhost:5173"
    qr_url = f"{base_url}/order/{new_token}"

    return QRTokenResponse(
        table_id=table.id,
        table_number=table.table_number,
        qr_token=new_token,
        qr_url=qr_url,
        created_at=table.qr_token_created_at,
    )


@router.get(
    "/{table_id}/qr-token",
    response_model=QRTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current table QR ordering token",
)
def get_table_qr_token(
    table_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve the currently active QR token and URL for a table."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID {table_id} not found.",
        )

    if not table.qr_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active QR token configured for Table '{table.table_number}'. Generate one first.",
        )

    base_url = "http://localhost:5173"
    qr_url = f"{base_url}/order/{table.qr_token}"

    return QRTokenResponse(
        table_id=table.id,
        table_number=table.table_number,
        qr_token=table.qr_token,
        qr_url=qr_url,
        created_at=table.qr_token_created_at,
    )


@router.delete(
    "/{table_id}/qr-token",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke table QR ordering token",
)
def revoke_table_qr_token(
    table_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Revoke and deactivate the QR ordering token for a table.

    - Customers attempting to order via the revoked token will receive HTTP 404.
    - Requires Manager or Admin role.
    """
    table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID {table_id} not found.",
        )

    table.qr_token = None
    table.qr_token_created_at = None

    try:
        db.commit()
        return None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke QR token.",
        )
