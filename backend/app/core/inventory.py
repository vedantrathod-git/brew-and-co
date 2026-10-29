from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient
from app.models.order import Order
from app.models.recipe import Recipe
from app.models.stock_movement import StockMovement
from app.models.user import User


def deduct_inventory_for_order(
    db: Session,
    order: Order,
    acting_user: Optional[User] = None,
) -> List[str]:
    """Transactionally deduct ingredient stock for an order entering confirmation/prep.

    Safeguards:
    1. Idempotency: If order.inventory_deducted is already True, no-op immediately.
    2. Missing Recipe Transparency: Returns operational warnings for dishes without recipes.
    3. Row-level concurrency locks (SELECT ... FOR UPDATE) on all target ingredients.
    4. Insufficient stock prevention: Rejects transition with HTTP 409 if any ingredient
       is inadequate, leaving zero partial deductions.
    5. Auditable ledger: Writes immutable 'order_consumption' movement rows.
    """
    if order.inventory_deducted:
        return []

    # 1. Aggregate required ingredient quantities across all order items
    required_ingredients: Dict[int, Decimal] = {}
    warnings: List[str] = []

    for item in order.order_items:
        recipes = db.query(Recipe).filter(Recipe.menu_item_id == item.menu_item_id).all()
        if not recipes:
            item_name = item.menu_item.name if item.menu_item else f"ID {item.menu_item_id}"
            warnings.append(
                f"Menu item '{item_name}' (ID {item.menu_item_id}) has no recipe configured. Skipped stock deduction."
            )
            continue

        for recipe in recipes:
            total_qty = recipe.quantity * Decimal(item.quantity)
            required_ingredients[recipe.ingredient_id] = (
                required_ingredients.get(recipe.ingredient_id, Decimal("0.000")) + total_qty
            )

    # If no items had recipes configured, mark as deducted so we don't re-scan on future transitions
    if not required_ingredients:
        order.inventory_deducted = True
        return warnings

    # 2. Acquire row-level locks on all involved ingredients to prevent concurrent over-allocation
    ingredient_ids = sorted(required_ingredients.keys())
    locked_ingredients = (
        db.query(Ingredient)
        .filter(Ingredient.id.in_(ingredient_ids))
        .with_for_update()
        .all()
    )
    ingredient_map = {ing.id: ing for ing in locked_ingredients}

    # Verify all ingredients exist and are active
    for ing_id, needed_qty in required_ingredients.items():
        ingredient = ingredient_map.get(ing_id)
        if not ingredient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Required recipe ingredient (ID {ing_id}) was not found in the inventory system.",
            )
        if not ingredient.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Required ingredient '{ingredient.name}' (ID {ing_id}) is currently deactivated.",
            )
        if ingredient.current_stock < needed_qty:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Insufficient inventory for '{ingredient.name}' (ID {ing_id}): "
                    f"required {needed_qty} {ingredient.unit}, available {ingredient.current_stock} {ingredient.unit}. "
                    f"Cannot confirm order without sufficient stock."
                ),
            )

    # 3. Apply deductions and record individual stock movements
    user_id = acting_user.id if acting_user else None
    for ing_id, needed_qty in required_ingredients.items():
        ingredient = ingredient_map[ing_id]
        ingredient.current_stock -= needed_qty

        movement = StockMovement(
            ingredient_id=ingredient.id,
            quantity_delta=-needed_qty,
            movement_type="order_consumption",
            reason=f"Consumed for Order #{order.order_number}",
            order_id=order.id,
            user_id=user_id,
        )
        db.add(movement)

    order.inventory_deducted = True
    return warnings


def reverse_inventory_for_order(
    db: Session,
    order: Order,
    acting_user: Optional[User] = None,
) -> bool:
    """Transactionally reverse previously deducted stock when an order is cancelled.

    Creates auditable compensating 'order_reversal' movements rather than deleting
    historical 'order_consumption' records.
    """
    if not order.inventory_deducted:
        return False

    # Find all consumption movements recorded for this order
    consumptions = (
        db.query(StockMovement)
        .filter(
            StockMovement.order_id == order.id,
            StockMovement.movement_type == "order_consumption",
        )
        .all()
    )

    if not consumptions:
        order.inventory_deducted = False
        return False

    # Lock ingredients and restore balances
    ingredient_ids = sorted(set(m.ingredient_id for m in consumptions))
    locked_ingredients = (
        db.query(Ingredient)
        .filter(Ingredient.id.in_(ingredient_ids))
        .with_for_update()
        .all()
    )
    ingredient_map = {ing.id: ing for ing in locked_ingredients}

    user_id = acting_user.id if acting_user else None
    for consumption in consumptions:
        ingredient = ingredient_map.get(consumption.ingredient_id)
        if ingredient:
            restore_qty = abs(consumption.quantity_delta)
            ingredient.current_stock += restore_qty

            compensating_movement = StockMovement(
                ingredient_id=ingredient.id,
                quantity_delta=restore_qty,
                movement_type="order_reversal",
                reason=f"Compensating reversal for cancelled Order #{order.order_number}",
                order_id=order.id,
                user_id=user_id,
            )
            db.add(compensating_movement)

    order.inventory_deducted = False
    return True


def adjust_ingredient_stock(
    db: Session,
    ingredient_id: int,
    adjustment_type: str,
    quantity: Decimal,
    reason: Optional[str] = None,
    acting_user: Optional[User] = None,
) -> StockMovement:
    """Safely adjust ingredient stock for restock delivery, waste/spoilage, or correction.

    Guarantees non-negative stock and writes to the movement ledger atomically.
    """
    if quantity <= Decimal("0.000"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Adjustment quantity must be greater than 0.",
        )

    ingredient = (
        db.query(Ingredient)
        .filter(Ingredient.id == ingredient_id)
        .with_for_update()
        .first()
    )
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with ID {ingredient_id} not found.",
        )

    if not ingredient.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot adjust stock for deactivated ingredient '{ingredient.name}'.",
        )

    if adjustment_type == "restock":
        delta = quantity
        default_reason = "Supplier delivery / restock"
    elif adjustment_type == "waste":
        delta = -quantity
        default_reason = "Kitchen waste / spoilage"
    elif adjustment_type == "manual_correction":
        delta = quantity  # Can be positive or negative based on caller
        default_reason = "Audited manual count correction"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported adjustment type '{adjustment_type}'.",
        )

    new_stock = ingredient.current_stock + delta
    if new_stock < Decimal("0.000"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Stock reduction of {abs(delta)} {ingredient.unit} would result in negative balance. "
                f"Current stock: {ingredient.current_stock} {ingredient.unit}."
            ),
        )

    ingredient.current_stock = new_stock

    user_id = acting_user.id if acting_user else None
    movement = StockMovement(
        ingredient_id=ingredient.id,
        quantity_delta=delta,
        movement_type=adjustment_type,
        reason=reason.strip() if reason and reason.strip() else default_reason,
        user_id=user_id,
    )
    db.add(movement)
    return movement
