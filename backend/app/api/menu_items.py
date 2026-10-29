from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_manager_or_admin, require_staff
from app.db.session import get_db
from app.models.category import Category
from app.models.menu_item import MenuItem
from app.models.order import OrderItem
from app.models.user import User
from app.schemas.menu_item import MenuItemCreate, MenuItemResponse, MenuItemUpdate

router = APIRouter(
    prefix="/api/menu-items",
    tags=["Menu Items"],
)


@router.post(
    "",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new menu item",
)
def create_menu_item(
    item_in: MenuItemCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Create a new menu item.

    - Validates that the referenced category exists (returns 404 if missing).
    - Checks that the dish name is unique (returns 409 if duplicate).
    - Returns 201 Created on success.
    """
    # 1. Verify category exists
    category = db.query(Category).filter(Category.id == item_in.category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {item_in.category_id} not found.",
        )

    # 2. Check for duplicate menu item name (case-insensitive)
    existing = db.query(MenuItem).filter(
        func.lower(MenuItem.name) == item_in.name.lower()
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Menu item with name '{item_in.name}' already exists.",
        )

    # 3. Create menu item
    new_item = MenuItem(
        category_id=item_in.category_id,
        name=item_in.name,
        description=item_in.description,
        price=item_in.price,
        is_available=item_in.is_available,
        prep_time_minutes=item_in.prep_time_minutes,
    )
    db.add(new_item)
    try:
        db.commit()
        db.refresh(new_item)
        # Eagerly attach category relationship for response serialization
        new_item.category = category
        return new_item
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Menu item with name '{item_in.name}' already exists or foreign key reference is invalid.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while creating the menu item.",
        )


@router.get(
    "",
    response_model=List[MenuItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List all menu items",
)
def list_menu_items(
    category_id: Optional[int] = Query(None, description="Filter items by category ID"),
    is_available: Optional[bool] = Query(None, description="Filter items by availability"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve all menu items with their category names eager-loaded.

    Supports optional filtering by category_id and is_available.
    """
    query = db.query(MenuItem).options(joinedload(MenuItem.category))

    if category_id is not None:
        query = query.filter(MenuItem.category_id == category_id)

    if is_available is not None:
        query = query.filter(MenuItem.is_available == is_available)

    items = query.order_by(MenuItem.id.asc()).all()
    return items


@router.get(
    "/{item_id}",
    response_model=MenuItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Get menu item by ID",
)
def get_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve a single menu item by its primary key ID."""
    item = (
        db.query(MenuItem)
        .options(joinedload(MenuItem.category))
        .filter(MenuItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item with ID {item_id} not found.",
        )
    return item


@router.put(
    "/{item_id}",
    response_model=MenuItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a menu item",
)
def update_menu_item(
    item_id: int,
    item_in: MenuItemUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Update a menu item's attributes.

    - Validates that the menu item exists (404).
    - Validates that the target category exists (404).
    - Checks for name collisions with other items (409).
    - Returns 200 OK with the updated menu item.
    """
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item with ID {item_id} not found.",
        )

    # Verify target category exists
    target_category = db.query(Category).filter(Category.id == item_in.category_id).first()
    if not target_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {item_in.category_id} not found.",
        )

    # Check for name collision with another menu item (case-insensitive)
    conflict = db.query(MenuItem).filter(
        func.lower(MenuItem.name) == item_in.name.lower(),
        MenuItem.id != item_id,
    ).first()
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another menu item with name '{item_in.name}' already exists.",
        )

    # Update item fields
    item.category_id = item_in.category_id
    item.name = item_in.name
    item.description = item_in.description
    item.price = item_in.price
    item.is_available = item_in.is_available
    item.prep_time_minutes = item_in.prep_time_minutes

    try:
        db.commit()
        db.refresh(item)
        item.category = target_category
        return item
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another menu item with name '{item_in.name}' already exists or category reference is invalid.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while updating the menu item.",
        )


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a menu item",
)
def delete_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Delete a menu item by ID.

    - Returns 204 No Content with an empty body on success.
    - Returns 404 if the item does not exist.
    - Returns 409 Conflict if historical order line items reference this dish.
    """
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item with ID {item_id} not found.",
        )

    # Enforce historical order data integrity: check if any OrderItems reference this dish
    referencing_orders_count = db.query(OrderItem).filter(OrderItem.menu_item_id == item_id).count()
    if referencing_orders_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete menu item '{item.name}' because {referencing_orders_count} "
                f"historical order record(s) reference it. Consider setting 'is_available=False' instead."
            ),
        )

    try:
        db.delete(item)
        db.commit()
        return None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete menu item '{item.name}' due to referencing records.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while deleting the menu item.",
        )
