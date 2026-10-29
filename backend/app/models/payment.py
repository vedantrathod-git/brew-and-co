from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class Payment(Base, TimestampMixin):
    """Payment transaction record associated with a café order."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'pending', 'authorized', 'captured', 'failed', 'refunded')",
            name="check_payment_status_valid",
        ),
        CheckConstraint(
            "amount >= 0 AND amount_paise >= 0",
            name="check_payment_amounts_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_reference: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        default="razorpay",
        server_default="razorpay",
        nullable=False,
    )
    provider_order_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )
    provider_payment_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )
    provider_signature: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="INR",
        server_default="INR",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="created",
        server_default="created",
        nullable=False,
    )
    method: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True,
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    error_description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    raw_response: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="payments")

    def __repr__(self) -> str:
        return (
            f"<Payment(id={self.id}, order_id={self.order_id}, "
            f"ref='{self.payment_reference}', status='{self.status}', "
            f"amount={self.amount} {self.currency})>"
        )


class ProcessedWebhookEvent(Base):
    """Audit table tracking processed Razorpay webhook events to guarantee idempotency."""

    __tablename__ = "processed_webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    entity_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProcessedWebhookEvent(event_id='{self.event_id}', type='{self.event_type}')>"
