"""add_qr_token_and_idempotency_key

Revision ID: e5f3a21b8c47
Revises: d2e9b04f1a23
Create Date: 2026-10-29 04:00:00.000000

Phase 21: Brew & Co. QR Table Ordering System:
- Adds 'qr_token' and 'qr_token_created_at' to 'restaurant_tables'
- Adds 'idempotency_key' to 'orders'
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f3a21b8c47'
down_revision: Union[str, Sequence[str], None] = 'd2e9b04f1a23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add qr_token and qr_token_created_at to restaurant_tables
    op.add_column(
        'restaurant_tables',
        sa.Column('qr_token', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'restaurant_tables',
        sa.Column('qr_token_created_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_restaurant_tables_qr_token',
        'restaurant_tables',
        ['qr_token'],
        unique=True,
    )

    # 2. Add idempotency_key to orders
    op.add_column(
        'orders',
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
    )
    op.create_index(
        'ix_orders_idempotency_key',
        'orders',
        ['idempotency_key'],
        unique=True,
    )


def downgrade() -> None:
    # 1. Drop orders idempotency_key
    op.drop_index('ix_orders_idempotency_key', table_name='orders')
    op.drop_column('orders', 'idempotency_key')

    # 2. Drop restaurant_tables qr_token columns
    op.drop_index('ix_restaurant_tables_qr_token', table_name='restaurant_tables')
    op.drop_column('restaurant_tables', 'qr_token_created_at')
    op.drop_column('restaurant_tables', 'qr_token')
