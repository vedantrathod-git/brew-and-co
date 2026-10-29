"""add_payment_tables_and_order_payment_status

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-10-28 22:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add payment_status and payment_method to orders
    op.add_column(
        'orders',
        sa.Column('payment_status', sa.String(length=20), server_default='pending', nullable=False)
    )
    op.add_column(
        'orders',
        sa.Column('payment_method', sa.String(length=32), nullable=True)
    )
    op.create_check_constraint(
        'check_order_payment_status_valid',
        'orders',
        "payment_status IN ('pending', 'paid', 'failed', 'refunded')"
    )

    # 2. Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('payment_reference', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=32), server_default='razorpay', nullable=False),
        sa.Column('provider_order_id', sa.String(length=64), nullable=True),
        sa.Column('provider_payment_id', sa.String(length=64), nullable=True),
        sa.Column('provider_signature', sa.String(length=128), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('amount_paise', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='created', nullable=False),
        sa.Column('method', sa.String(length=32), nullable=True),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_description', sa.String(length=255), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN ('created', 'pending', 'authorized', 'captured', 'failed', 'refunded')",
            name='check_payment_status_valid'
        ),
        sa.CheckConstraint(
            "amount >= 0 AND amount_paise >= 0",
            name='check_payment_amounts_non_negative'
        )
    )
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=False)
    op.create_index(op.f('ix_payments_payment_reference'), 'payments', ['payment_reference'], unique=True)
    op.create_index(op.f('ix_payments_provider_order_id'), 'payments', ['provider_order_id'], unique=False)
    op.create_index(op.f('ix_payments_provider_payment_id'), 'payments', ['provider_payment_id'], unique=False)
    op.create_index(op.f('ix_payments_idempotency_key'), 'payments', ['idempotency_key'], unique=True)

    # 3. Create processed_webhook_events table
    op.create_table(
        'processed_webhook_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_processed_webhook_events_event_id'), 'processed_webhook_events', ['event_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_processed_webhook_events_event_id'), table_name='processed_webhook_events')
    op.drop_table('processed_webhook_events')

    op.drop_index(op.f('ix_payments_idempotency_key'), table_name='payments')
    op.drop_index(op.f('ix_payments_provider_payment_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_provider_order_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_payment_reference'), table_name='payments')
    op.drop_index(op.f('ix_payments_order_id'), table_name='payments')
    op.drop_table('payments')

    op.drop_constraint('check_order_payment_status_valid', 'orders', type_='check')
    op.drop_column('orders', 'payment_method')
    op.drop_column('orders', 'payment_status')
