from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import require_manager_or_admin, require_staff
from app.db.session import get_db
from app.models.category import Category
from app.models.menu_item import MenuItem
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(
    prefix="/api/categories",
    tags=["Categories"],
)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new category",
)
def create_category(
    category_in: CategoryCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Create a new category.

    Returns 201 on success.
    Returns 409 if a category with the same name already exists.
    """
    # Proactive case-insensitive duplicate check
    existing = db.query(Category).filter(
        func.lower(Category.name) == category_in.name.lower()
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with name '{category_in.name}' already exists.",
        )

    new_category = Category(
        name=category_in.name,
        description=category_in.description,
    )
    db.add(new_category)
    try:
        db.commit()
        db.refresh(new_category)
        return new_category
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with name '{category_in.name}' already exists.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while creating the category.",
        )


@router.get(
    "",
    response_model=List[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List all categories",
)
def list_categories(
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve all categories ordered by ID."""
    categories = db.query(Category).order_by(Category.id.asc()).all()
    return categories


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get category by ID",
)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve a single category by its primary key ID.

    Returns 404 if the category does not exist.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {category_id} not found.",
        )
    return category


@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a category",
)
def update_category(
    category_id: int,
    category_in: CategoryUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Update a category's name and description.

    Returns 200 on success.
    Returns 404 if the category is not found.
    Returns 409 if the updated name conflicts with another category.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {category_id} not found.",
        )

    # Check for name collision with other existing categories (case-insensitive)
    conflict = db.query(Category).filter(
        func.lower(Category.name) == category_in.name.lower(),
        Category.id != category_id,
    ).first()
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another category with name '{category_in.name}' already exists.",
        )

    category.name = category_in.name
    category.description = category_in.description

    try:
        db.commit()
        db.refresh(category)
        return category
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another category with name '{category_in.name}' already exists.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while updating the category.",
        )


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category",
)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Delete a category by its ID.

    Returns 204 on successful deletion with an empty body.
    Returns 404 if the category does not exist.
    Returns 409 if the category is referenced by one or more menu items.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {category_id} not found.",
        )

    # Clean foreign-key check: check if menu items reference this category
    referencing_items_count = db.query(MenuItem).filter(MenuItem.category_id == category_id).count()
    if referencing_items_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete category '{category.name}' because {referencing_items_count} "
                f"menu item(s) reference it. Please reassign or delete the associated menu items first."
            ),
        )

    try:
        db.delete(category)
        db.commit()
        return None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete category '{category.name}' due to referencing records.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while deleting the category.",
        )
