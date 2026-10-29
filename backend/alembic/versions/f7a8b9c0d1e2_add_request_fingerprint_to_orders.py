"""add_request_fingerprint_to_orders

Revision ID: f7a8b9c0d1e2
Revises: e5f3a21b8c47
Create Date: 2026-10-29 05:00:00.000000

Phase 21: Brew & Co. QR Table Ordering System:
- Adds 'request_fingerprint' (String(64)) to 'orders' table to verify payload consistency
  when duplicate idempotency keys are submitted.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'e5f3a21b8c47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'orders',
        sa.Column('request_fingerprint', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('orders', 'request_fingerprint')
