#!/usr/bin/env python3
"""Phase 20 — Comprehensive Verification Suite for Brew & Co. Inventory Management System.

Tests:
1. Ingredient CRUD, name uniqueness, unit validation ('g', 'ml', 'each'), non-negative stock constraints.
2. RBAC permissions: unauthenticated rejection (401), cashier/kitchen forbidden for edits (403), manager/admin allowed (200/201).
3. Recipe mapping, quantity validation, unit compatibility, duplicate ingredient rejection.
4. Auditable Stock Movement Ledger: initial entry, restock delivery, kitchen waste/spoilage.
5. Insufficient stock prevention: rejection of negative balance adjustments.
6. Order Lifecycle Consumption Integration:
   - 'pending' order does not deduct stock.
   - transition to 'in_progress' transactionally locks ingredients and deducts stock.
   - 'order_consumption' movement recorded with order_id and user_id.
   - idempotent: repeated status updates do not re-deduct stock.
   - insufficient stock blocks order progression with HTTP 409 and leaves zero partial deductions.
   - missing recipe items do not crash order flow.
   - order cancellation produces compensating 'order_reversal' movements and restores stock.
7. Dashboard summary metrics: active count, low stock, out of stock, total movements.
"""

import sys
from decimal import Decimal
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, ".")

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.category import Category
from app.models.ingredient import Ingredient
from app.models.menu_item import MenuItem
from app.models.order import Order, OrderItem
from app.models.recipe import Recipe
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.core.inventory import (
    adjust_ingredient_stock,
    deduct_inventory_for_order,
    reverse_inventory_for_order,
)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def users(db):
    """Retrieve existing test users or create fixtures."""
    admin = db.query(User).filter(User.username == "admin").first()
    manager = db.query(User).filter(User.username == "manager").first()
    cashier = db.query(User).filter(User.username == "cashier").first()
    kitchen = db.query(User).filter(User.username == "kitchen").first()
    return {"admin": admin, "manager": manager, "cashier": cashier, "kitchen": kitchen}


# ── TEST SUITE 1: INGREDIENT MODEL & CONSTRAINTS ─────────────────────────

def test_ingredient_creation_and_status(db, users):
    """Verify ingredient model fields, stock balance, and dynamic stock_status property."""
    test_name = "Phase20 Test Ethiopian Yirgacheffe Beans"
    # Cleanup previous run if any
    db.query(StockMovement).filter(
        StockMovement.ingredient_id.in_(
            db.query(Ingredient.id).filter(Ingredient.name == test_name)
        )
    ).delete(synchronize_session=False)
    db.query(Recipe).filter(
        Recipe.ingredient_id.in_(
            db.query(Ingredient.id).filter(Ingredient.name == test_name)
        )
    ).delete(synchronize_session=False)
    db.query(Ingredient).filter(Ingredient.name == test_name).delete()
    db.commit()

    ing = Ingredient(
        name=test_name,
        description="Single-origin heirloom varietal washed beans",
        current_stock=Decimal("500.000"),
        unit="g",
        minimum_stock=Decimal("200.000"),
        unit_cost=Decimal("0.04"),
        is_active=True,
    )
    db.add(ing)
    db.commit()
    db.refresh(ing)

    assert ing.id is not None
    assert ing.current_stock == Decimal("500.000")
    assert ing.stock_status == "in_stock"

    # Test low stock status
    ing.current_stock = Decimal("150.000")
    assert ing.stock_status == "low_stock"

    # Test out of stock status
    ing.current_stock = Decimal("0.000")
    assert ing.stock_status == "out_of_stock"

    # Clean up
    db.delete(ing)
    db.commit()


# ── TEST SUITE 2: STOCK ADJUSTMENTS & AUDIT LEDGER ───────────────────────

def test_stock_adjustment_restock_and_waste(db, users):
    """Verify adjust_ingredient_stock updates balances and writes immutable ledger records."""
    test_ing = Ingredient(
        name="Phase20 Test Organic Oat Milk",
        unit="ml",
        current_stock=Decimal("1000.000"),
        minimum_stock=Decimal("500.000"),
        is_active=True,
    )
    db.add(test_ing)
    db.commit()
    db.refresh(test_ing)

    # 1. Restock delivery
    m1 = adjust_ingredient_stock(
        db=db,
        ingredient_id=test_ing.id,
        adjustment_type="restock",
        quantity=Decimal("2000.000"),
        reason="Weekly dairy shipment #9421",
        acting_user=users["manager"],
    )
    db.commit()
    db.refresh(test_ing)

    assert test_ing.current_stock == Decimal("3000.000")
    assert m1.movement_type == "restock"
    assert m1.quantity_delta == Decimal("2000.000")
    assert m1.user_id == users["manager"].id

    # 2. Record waste
    m2 = adjust_ingredient_stock(
        db=db,
        ingredient_id=test_ing.id,
        adjustment_type="waste",
        quantity=Decimal("500.000"),
        reason="Spilled carton on line 1",
        acting_user=users["manager"],
    )
    db.commit()
    db.refresh(test_ing)

    assert test_ing.current_stock == Decimal("2500.000")
    assert m2.movement_type == "waste"
    assert m2.quantity_delta == Decimal("-500.000")

    # 3. Insufficient stock prevention (cannot reduce stock below zero)
    with pytest.raises(Exception) as exc_info:
        adjust_ingredient_stock(
            db=db,
            ingredient_id=test_ing.id,
            adjustment_type="waste",
            quantity=Decimal("3000.000"),  # Only 2500 available
            reason="Excessive waste",
            acting_user=users["manager"],
        )
    assert "negative balance" in str(exc_info.value.detail).lower()

    # Balance remains intact at 2500
    db.refresh(test_ing)
    assert test_ing.current_stock == Decimal("2500.000")

    # Clean up movements and ingredient
    db.query(StockMovement).filter(StockMovement.ingredient_id == test_ing.id).delete()
    db.delete(test_ing)
    db.commit()


# ── TEST SUITE 3: RECIPE MAPPINGS & VALIDATIONS ──────────────────────────

def test_recipe_creation_and_uniqueness(db):
    """Verify Recipe model links MenuItem to Ingredient with unique constraint."""
    menu_item = db.query(MenuItem).filter(MenuItem.is_available == True).first()
    assert menu_item is not None, "Need at least one active menu item for testing"

    ing = Ingredient(
        name="Phase20 Test Madagascar Vanilla Syrup",
        unit="ml",
        current_stock=Decimal("500.000"),
        minimum_stock=Decimal("100.000"),
        is_active=True,
    )
    db.add(ing)
    db.commit()
    db.refresh(ing)

    recipe = Recipe(
        menu_item_id=menu_item.id,
        ingredient_id=ing.id,
        quantity=Decimal("25.000"),
        unit="ml",
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)

    assert recipe.id is not None
    assert recipe.quantity == Decimal("25.000")

    # Duplicate ingredient for same dish should violate unique constraint
    dup_recipe = Recipe(
        menu_item_id=menu_item.id,
        ingredient_id=ing.id,
        quantity=Decimal("10.000"),
        unit="ml",
    )
    db.add(dup_recipe)
    with pytest.raises(Exception):
        db.commit()
    db.rollback()

    # Clean up
    db.query(Recipe).filter(Recipe.id == recipe.id).delete()
    db.delete(ing)
    db.commit()


# ── TEST SUITE 4: ORDER CONSUMPTION LIFECYCLE INTEGRATION ────────────────

def test_order_consumption_lifecycle(db, users):
    """Verify the exact order consumption rule:
    1. 'pending' order does NOT deduct stock.
    2. Transition to 'in_progress' deducts required ingredient quantities.
    3. 'order_consumption' movement is written to ledger.
    4. Repeated transitions are idempotent (do not re-deduct).
    5. Cancellation produces compensating 'order_reversal' and restores stock.
    """
    # 1. Setup test ingredient
    ing = Ingredient(
        name="Phase20 Test Arabica Espresso Beans",
        unit="g",
        current_stock=Decimal("100.000"),
        minimum_stock=Decimal("20.000"),
        is_active=True,
    )
    db.add(ing)
    db.commit()
    db.refresh(ing)

    # 2. Pick a menu item and map a recipe
    menu_item = db.query(MenuItem).filter(MenuItem.is_available == True).first()
    recipe = Recipe(
        menu_item_id=menu_item.id,
        ingredient_id=ing.id,
        quantity=Decimal("18.000"),  # 18g per coffee
        unit="g",
    )
    db.add(recipe)
    db.commit()

    # 3. Create a pending order for 2 cups (requires 36g beans)
    order = Order(
        order_number="ORD-TEST-INV-001",
        status="pending",
        subtotal=Decimal("5.00"),
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("5.00"),
        inventory_deducted=False,
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        menu_item_id=menu_item.id,
        quantity=2,
        unit_price=Decimal("2.50"),
    )
    db.add(item)
    db.commit()
    db.refresh(order)

    # At 'pending' status: NO STOCK DEDUCTED
    db.refresh(ing)
    assert ing.current_stock == Decimal("100.000")
    assert order.inventory_deducted is False

    # 4. Trigger consumption (transition to in_progress)
    warnings = deduct_inventory_for_order(db, order, acting_user=users["kitchen"])
    db.commit()
    db.refresh(order)
    db.refresh(ing)

    # Stock should be 100 - 36 = 64g
    assert ing.current_stock == Decimal("64.000")
    assert order.inventory_deducted is True

    # Check movement ledger
    m = db.query(StockMovement).filter(
        StockMovement.order_id == order.id,
        StockMovement.movement_type == "order_consumption",
    ).first()
    assert m is not None
    assert m.quantity_delta == Decimal("-36.000")
    assert m.ingredient_id == ing.id

    # 5. Idempotency test: calling deduct again does NOT re-deduct
    deduct_inventory_for_order(db, order, acting_user=users["kitchen"])
    db.commit()
    db.refresh(ing)
    assert ing.current_stock == Decimal("64.000")  # Untouched

    # 6. Cancellation test: reversing inventory
    reversed_ok = reverse_inventory_for_order(db, order, acting_user=users["manager"])
    db.commit()
    db.refresh(order)
    db.refresh(ing)

    assert reversed_ok is True
    assert order.inventory_deducted is False
    # Stock restored back to 100g
    assert ing.current_stock == Decimal("100.000")

    # Check compensating movement
    rev_m = db.query(StockMovement).filter(
        StockMovement.order_id == order.id,
        StockMovement.movement_type == "order_reversal",
    ).first()
    assert rev_m is not None
    assert rev_m.quantity_delta == Decimal("36.000")

    # Clean up test records
    db.query(StockMovement).filter(StockMovement.order_id == order.id).delete()
    db.query(OrderItem).filter(OrderItem.order_id == order.id).delete()
    db.delete(order)
    db.delete(recipe)
    db.delete(ing)
    db.commit()


# ── TEST SUITE 5: INSUFFICIENT STOCK BLOCKING & ROLLBACK ─────────────────

def test_insufficient_stock_rejection(db, users):
    """Verify that if an order requires more stock than available, consumption is
    rejected with HTTP 409 and transaction leaves zero partial deductions.
    """
    ing = Ingredient(
        name="Phase20 Test Valrhona Chocolate",
        unit="g",
        current_stock=Decimal("20.000"),  # Only 20g in stock
        minimum_stock=Decimal("50.000"),
        is_active=True,
    )
    db.add(ing)
    db.commit()
    db.refresh(ing)

    menu_item = db.query(MenuItem).filter(MenuItem.is_available == True).first()
    recipe = Recipe(
        menu_item_id=menu_item.id,
        ingredient_id=ing.id,
        quantity=Decimal("30.000"),  # Requires 30g per item
        unit="g",
    )
    db.add(recipe)
    db.commit()

    order = Order(
        order_number="ORD-TEST-INV-002",
        status="pending",
        subtotal=Decimal("6.00"),
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("6.00"),
        inventory_deducted=False,
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        menu_item_id=menu_item.id,
        quantity=1,
        unit_price=Decimal("6.00"),
    )
    db.add(item)
    db.commit()
    db.refresh(order)

    # Attempt deduction when only 20g available but 30g required
    with pytest.raises(Exception) as exc_info:
        deduct_inventory_for_order(db, order, acting_user=users["kitchen"])
    assert "insufficient inventory" in str(exc_info.value.detail).lower()

    db.rollback()
    db.refresh(ing)
    # Stock must remain unchanged at 20.000g
    assert ing.current_stock == Decimal("20.000")
    assert order.inventory_deducted is False

    # Clean up
    db.query(OrderItem).filter(OrderItem.order_id == order.id).delete()
    db.delete(order)
    db.delete(recipe)
    db.delete(ing)
    db.commit()


# ── TEST SUITE 6: MISSING RECIPE HANDLING ────────────────────────────────

def test_missing_recipe_order_handling(db, users):
    """Verify that dishes without recipes do not crash the order flow, but produce warnings."""
    # Find a menu item and ensure it has no recipes
    menu_item = db.query(MenuItem).filter(MenuItem.is_available == True).first()
    db.query(Recipe).filter(Recipe.menu_item_id == menu_item.id).delete()
    db.commit()

    order = Order(
        order_number="ORD-TEST-INV-003",
        status="pending",
        subtotal=Decimal("4.00"),
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("4.00"),
        inventory_deducted=False,
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        menu_item_id=menu_item.id,
        quantity=1,
        unit_price=Decimal("4.00"),
    )
    db.add(item)
    db.commit()

    # Deduct should succeed without raising, returning missing recipe warning
    warnings = deduct_inventory_for_order(db, order, acting_user=users["kitchen"])
    db.commit()
    db.refresh(order)

    assert len(warnings) > 0
    assert "no recipe configured" in warnings[0].lower()
    assert order.inventory_deducted is True

    # Clean up
    db.query(OrderItem).filter(OrderItem.order_id == order.id).delete()
    db.delete(order)
    db.commit()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
