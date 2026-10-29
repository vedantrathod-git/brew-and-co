from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_manager_or_admin, require_staff
from app.core.inventory import adjust_ingredient_stock
from app.db.session import get_db
from app.models.category import Category
from app.models.ingredient import Ingredient
from app.models.menu_item import MenuItem
from app.models.recipe import Recipe
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.inventory import (
    IngredientCreate,
    IngredientResponse,
    IngredientStockAdjustment,
    IngredientUpdate,
    InventorySummaryResponse,
    MenuItemRecipeResponse,
    RecipeItemCreate,
    RecipeItemResponse,
    RecipeItemUpdate,
    StockMovementResponse,
)

router = APIRouter(
    prefix="/api/inventory",
    tags=["Inventory"],
)


def _build_ingredient_response(ing: Ingredient) -> dict:
    return {
        "id": ing.id,
        "name": ing.name,
        "description": ing.description,
        "current_stock": ing.current_stock,
        "unit": ing.unit,
        "minimum_stock": ing.minimum_stock,
        "unit_cost": ing.unit_cost,
        "is_active": ing.is_active,
        "stock_status": ing.stock_status,
        "created_at": ing.created_at,
        "updated_at": ing.updated_at,
    }


def _build_movement_response(m: StockMovement) -> dict:
    return {
        "id": m.id,
        "ingredient_id": m.ingredient_id,
        "ingredient_name": m.ingredient.name if m.ingredient else None,
        "ingredient_unit": m.ingredient.unit if m.ingredient else None,
        "quantity_delta": m.quantity_delta,
        "movement_type": m.movement_type,
        "reason": m.reason,
        "order_id": m.order_id,
        "user_id": m.user_id,
        "user_name": m.user.full_name or m.user.username if m.user else None,
        "created_at": m.created_at,
    }


def _build_recipe_item_response(r: Recipe) -> dict:
    return {
        "id": r.id,
        "menu_item_id": r.menu_item_id,
        "menu_item_name": r.menu_item.name if r.menu_item else None,
        "ingredient_id": r.ingredient_id,
        "ingredient_name": r.ingredient.name if r.ingredient else None,
        "ingredient_unit": r.ingredient.unit if r.ingredient else None,
        "quantity": r.quantity,
        "unit": r.unit,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


# ── Dashboard Summary ────────────────────────────────────────────────────

@router.get(
    "/dashboard-summary",
    response_model=InventorySummaryResponse,
    summary="Get inventory summary metrics",
)
def get_inventory_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Return top-level inventory health metrics."""
    ingredients = db.query(Ingredient).filter(Ingredient.is_active == True).all()
    total_active = len(ingredients)
    low_stock = sum(1 for i in ingredients if i.stock_status == "low_stock")
    out_of_stock = sum(1 for i in ingredients if i.stock_status == "out_of_stock")
    total_movements = db.query(func.count(StockMovement.id)).scalar() or 0

    return {
        "total_active_ingredients": total_active,
        "low_stock_count": low_stock,
        "out_of_stock_count": out_of_stock,
        "total_movements_recorded": total_movements,
    }


# ── Ingredient Management (CRUD) ─────────────────────────────────────────

@router.get(
    "/ingredients",
    response_model=List[IngredientResponse],
    summary="List all inventory ingredients",
)
def list_ingredients(
    search: Optional[str] = Query(None, description="Search ingredients by name or description"),
    stock_status: Optional[str] = Query(None, description="Filter by stock status: in_stock, low_stock, out_of_stock"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """List ingredients with optional text search and stock-status filter."""
    query = db.query(Ingredient)

    if is_active is not None:
        query = query.filter(Ingredient.is_active == is_active)

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            func.lower(Ingredient.name).like(term) | func.lower(Ingredient.description).like(term)
        )

    ingredients = query.order_by(Ingredient.name.asc()).all()

    # Filter by computed stock_status if requested
    if stock_status in ("in_stock", "low_stock", "out_of_stock"):
        ingredients = [i for i in ingredients if i.stock_status == stock_status]

    return [_build_ingredient_response(i) for i in ingredients]


@router.get(
    "/ingredients/{ingredient_id}",
    response_model=IngredientResponse,
    summary="Get ingredient by ID",
)
def get_ingredient(
    ingredient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve detailed metadata and stock level for a single ingredient."""
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with ID {ingredient_id} not found.",
        )
    return _build_ingredient_response(ingredient)


@router.post(
    "/ingredients",
    response_model=IngredientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ingredient",
)
def create_ingredient(
    item_in: IngredientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_admin),
):
    """Create a new ingredient with optional initial stock. Writes initial movement if stock > 0."""
    existing = db.query(Ingredient).filter(func.lower(Ingredient.name) == item_in.name.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An ingredient named '{item_in.name}' already exists.",
        )

    new_ingredient = Ingredient(
        name=item_in.name,
        description=item_in.description,
        current_stock=item_in.initial_stock,
        unit=item_in.unit,
        minimum_stock=item_in.minimum_stock,
        unit_cost=item_in.unit_cost,
        is_active=True,
    )
    db.add(new_ingredient)

    try:
        db.flush()

        if item_in.initial_stock > Decimal("0.000"):
            init_movement = StockMovement(
                ingredient_id=new_ingredient.id,
                quantity_delta=item_in.initial_stock,
                movement_type="initial",
                reason="Initial inventory entry upon ingredient creation",
                user_id=user.id,
            )
            db.add(init_movement)

        db.commit()
        db.refresh(new_ingredient)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ingredient '{item_in.name}' violates a unique database constraint.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while creating the ingredient.",
        )

    return _build_ingredient_response(new_ingredient)


@router.put(
    "/ingredients/{ingredient_id}",
    response_model=IngredientResponse,
    summary="Update ingredient metadata",
)
def update_ingredient(
    ingredient_id: int,
    item_in: IngredientUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Update ingredient metadata, safety thresholds, or active state."""
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with ID {ingredient_id} not found.",
        )

    if item_in.name is not None and item_in.name.lower() != ingredient.name.lower():
        existing = db.query(Ingredient).filter(
            func.lower(Ingredient.name) == item_in.name.lower(),
            Ingredient.id != ingredient_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another ingredient named '{item_in.name}' already exists.",
            )
        ingredient.name = item_in.name

    if item_in.description is not None:
        ingredient.description = item_in.description
    if item_in.unit is not None:
        # Check if unit change is compatible with existing recipes
        recipes_count = db.query(Recipe).filter(Recipe.ingredient_id == ingredient_id).count()
        if recipes_count > 0 and item_in.unit != ingredient.unit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot change unit of '{ingredient.name}' because it is referenced by {recipes_count} recipe line(s).",
            )
        ingredient.unit = item_in.unit
    if item_in.minimum_stock is not None:
        ingredient.minimum_stock = item_in.minimum_stock
    if item_in.unit_cost is not None:
        ingredient.unit_cost = item_in.unit_cost
    if item_in.is_active is not None:
        ingredient.is_active = item_in.is_active

    try:
        db.commit()
        db.refresh(ingredient)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update violates database constraints.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while updating the ingredient.",
        )

    return _build_ingredient_response(ingredient)


@router.delete(
    "/ingredients/{ingredient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate or safely delete an ingredient",
)
def delete_ingredient(
    ingredient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Deactivate ingredient if referenced by recipes or stock movements; hard-delete only if unused."""
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with ID {ingredient_id} not found.",
        )

    recipes_count = db.query(Recipe).filter(Recipe.ingredient_id == ingredient_id).count()
    movements_count = db.query(StockMovement).filter(StockMovement.ingredient_id == ingredient_id).count()

    try:
        if recipes_count > 0 or movements_count > 0:
            # Soft deactivation preserves historical audits and foreign key integrity
            ingredient.is_active = False
            db.commit()
        else:
            db.delete(ingredient)
            db.commit()
        return None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while deleting the ingredient.",
        )


# ── Stock Adjustments (Restock / Waste / Correction) ─────────────────────

@router.post(
    "/ingredients/{ingredient_id}/adjust",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Perform a stock adjustment (restock, waste, correction)",
)
def adjust_stock(
    ingredient_id: int,
    adj_in: IngredientStockAdjustment,
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_admin),
):
    """Perform a transactional stock adjustment and write to the audit ledger."""
    try:
        movement = adjust_ingredient_stock(
            db=db,
            ingredient_id=ingredient_id,
            adjustment_type=adj_in.adjustment_type,
            quantity=adj_in.quantity,
            reason=adj_in.reason,
            acting_user=user,
        )
        db.commit()
        db.refresh(movement)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while recording the stock adjustment.",
        )

    # Reload with relationships
    movement = (
        db.query(StockMovement)
        .options(
            joinedload(StockMovement.ingredient),
            joinedload(StockMovement.user),
        )
        .filter(StockMovement.id == movement.id)
        .first()
    )
    return _build_movement_response(movement)


# ── Stock Movement Ledger ────────────────────────────────────────────────

@router.get(
    "/movements",
    response_model=List[StockMovementResponse],
    summary="Browse stock movement history",
)
def list_stock_movements(
    ingredient_id: Optional[int] = Query(None, description="Filter by ingredient ID"),
    movement_type: Optional[str] = Query(None, description="Filter by movement type"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Retrieve paginated stock movement ledger entries with optional filters."""
    query = (
        db.query(StockMovement)
        .options(
            joinedload(StockMovement.ingredient),
            joinedload(StockMovement.user),
        )
    )

    if ingredient_id is not None:
        query = query.filter(StockMovement.ingredient_id == ingredient_id)
    if movement_type is not None:
        query = query.filter(StockMovement.movement_type == movement_type)

    movements = query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).offset(offset).limit(limit).all()
    return [_build_movement_response(m) for m in movements]


# ── Recipe Management ────────────────────────────────────────────────────

@router.get(
    "/recipes",
    response_model=List[MenuItemRecipeResponse],
    summary="List all menu items with recipe configurations",
)
def list_all_recipes(
    category_id: Optional[int] = Query(None, description="Filter by menu item category ID"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Return all active menu items and their configured recipe ingredients."""
    query = (
        db.query(MenuItem)
        .options(
            joinedload(MenuItem.category),
            joinedload(MenuItem.recipes).joinedload(Recipe.ingredient),
        )
        .filter(MenuItem.is_available == True)
    )

    if category_id is not None:
        query = query.filter(MenuItem.category_id == category_id)

    menu_items = query.order_by(MenuItem.name.asc()).all()

    # Deduplicate due to joinedload
    seen = set()
    result = []
    for mi in menu_items:
        if mi.id in seen:
            continue
        seen.add(mi.id)

        items_resp = [_build_recipe_item_response(r) for r in mi.recipes]
        result.append({
            "menu_item_id": mi.id,
            "menu_item_name": mi.name,
            "category_name": mi.category_name,
            "has_recipe": len(items_resp) > 0,
            "recipe_items": items_resp,
        })

    return result


@router.get(
    "/recipes/menu-item/{menu_item_id}",
    response_model=MenuItemRecipeResponse,
    summary="Get recipe for a specific menu item",
)
def get_menu_item_recipe(
    menu_item_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Retrieve recipe line items for a specific menu item."""
    mi = (
        db.query(MenuItem)
        .options(
            joinedload(MenuItem.category),
            joinedload(MenuItem.recipes).joinedload(Recipe.ingredient),
        )
        .filter(MenuItem.id == menu_item_id)
        .first()
    )
    if not mi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item with ID {menu_item_id} not found.",
        )

    items_resp = [_build_recipe_item_response(r) for r in mi.recipes]
    return {
        "menu_item_id": mi.id,
        "menu_item_name": mi.name,
        "category_name": mi.category_name,
        "has_recipe": len(items_resp) > 0,
        "recipe_items": items_resp,
    }


@router.post(
    "/recipes",
    response_model=RecipeItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an ingredient to a menu item's recipe",
)
def add_recipe_item(
    item_in: RecipeItemCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Add a required ingredient and quantity to a menu item's recipe."""
    # Validate menu item exists
    mi = db.query(MenuItem).filter(MenuItem.id == item_in.menu_item_id).first()
    if not mi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item with ID {item_in.menu_item_id} not found.",
        )

    # Validate ingredient exists and is active
    ing = db.query(Ingredient).filter(Ingredient.id == item_in.ingredient_id).first()
    if not ing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with ID {item_in.ingredient_id} not found.",
        )
    if not ing.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ingredient '{ing.name}' is deactivated and cannot be added to recipes.",
        )

    # Unit compatibility check
    if item_in.unit != ing.unit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unit mismatch: Ingredient '{ing.name}' is measured in '{ing.unit}', but recipe specified '{item_in.unit}'.",
        )

    # Duplicate check
    existing = db.query(Recipe).filter(
        Recipe.menu_item_id == item_in.menu_item_id,
        Recipe.ingredient_id == item_in.ingredient_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ingredient '{ing.name}' is already in the recipe for '{mi.name}'. Update its quantity instead.",
        )

    new_recipe = Recipe(
        menu_item_id=item_in.menu_item_id,
        ingredient_id=item_in.ingredient_id,
        quantity=item_in.quantity,
        unit=item_in.unit,
    )
    db.add(new_recipe)

    try:
        db.commit()
        db.refresh(new_recipe)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recipe line violates database unique constraint.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while creating the recipe item.",
        )

    # Reload with relationships
    recipe = (
        db.query(Recipe)
        .options(
            joinedload(Recipe.menu_item),
            joinedload(Recipe.ingredient),
        )
        .filter(Recipe.id == new_recipe.id)
        .first()
    )
    return _build_recipe_item_response(recipe)


@router.delete(
    "/recipes/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an ingredient from a recipe",
)
def delete_recipe_item(
    recipe_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_admin),
):
    """Remove a specific ingredient line from a menu item's recipe."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe item with ID {recipe_id} not found.",
        )

    try:
        db.delete(recipe)
        db.commit()
        return None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while deleting the recipe item.",
        )
