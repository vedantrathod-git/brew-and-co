"""create_inventory_tables

Revision ID: d2e9b04f1a23
Revises: c1f8a92e4b3d
Create Date: 2026-10-29 03:00:00.000000

Phase 20: Brew & Co. Inventory Management System:
- Creates 'ingredients' table with decimal stock balances, minimum thresholds, and unit constraints
- Creates 'recipes' table mapping menu items to ingredients and quantities
- Creates 'stock_movements' auditable transaction ledger for stock adjustments and consumption
- Adds 'inventory_deducted' flag to 'orders' table to ensure idempotent, single consumption
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd2e9b04f1a23'
down_revision: Union[str, Sequence[str], None] = 'c1f8a92e4b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create ingredients table
    op.create_table(
        'ingredients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('current_stock', sa.Numeric(precision=12, scale=3), server_default='0.000', nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('minimum_stock', sa.Numeric(precision=12, scale=3), server_default='0.000', nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('current_stock >= 0', name='check_ingredient_current_stock_non_negative'),
        sa.CheckConstraint('minimum_stock >= 0', name='check_ingredient_minimum_stock_non_negative'),
        sa.CheckConstraint("unit IN ('g', 'ml', 'each')", name='check_ingredient_unit_valid'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ingredients_name', 'ingredients', ['name'], unique=True)

    # 2. Create recipes table
    op.create_table(
        'recipes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('menu_item_id', sa.Integer(), nullable=False),
        sa.Column('ingredient_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('quantity > 0', name='check_recipe_quantity_positive'),
        sa.CheckConstraint("unit IN ('g', 'ml', 'each')", name='check_recipe_unit_valid'),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('menu_item_id', 'ingredient_id', name='uq_recipe_menu_item_ingredient'),
    )
    op.create_index('ix_recipes_menu_item_id', 'recipes', ['menu_item_id'], unique=False)
    op.create_index('ix_recipes_ingredient_id', 'recipes', ['ingredient_id'], unique=False)

    # 3. Create stock_movements table
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ingredient_id', sa.Integer(), nullable=False),
        sa.Column('quantity_delta', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('movement_type', sa.String(length=30), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "movement_type IN ('initial', 'restock', 'manual_correction', 'waste', 'order_consumption', 'order_reversal')",
            name='check_stock_movement_type_valid',
        ),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_stock_movements_ingredient_id', 'stock_movements', ['ingredient_id'], unique=False)
    op.create_index('ix_stock_movements_order_id', 'stock_movements', ['order_id'], unique=False)
    op.create_index('ix_stock_movements_created_at', 'stock_movements', ['created_at'], unique=False)

    # 4. Add inventory_deducted column to orders table
    op.add_column(
        'orders',
        sa.Column('inventory_deducted', sa.Boolean(), server_default='false', nullable=False),
    )


def downgrade() -> None:
    # 4. Remove inventory_deducted column from orders
    op.drop_column('orders', 'inventory_deducted')

    # 3. Drop stock_movements table
    op.drop_index('ix_stock_movements_created_at', table_name='stock_movements')
    op.drop_index('ix_stock_movements_order_id', table_name='stock_movements')
    op.drop_index('ix_stock_movements_ingredient_id', table_name='stock_movements')
    op.drop_table('stock_movements')

    # 2. Drop recipes table
    op.drop_index('ix_recipes_ingredient_id', table_name='recipes')
    op.drop_index('ix_recipes_menu_item_id', table_name='recipes')
    op.drop_table('recipes')

    # 1. Drop ingredients table
    op.drop_index('ix_ingredients_name', table_name='ingredients')
    op.drop_table('ingredients')
