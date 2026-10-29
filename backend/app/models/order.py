from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.menu_item import MenuItem
    from app.models.table import RestaurantTable
    from app.models.payment import Payment


class Order(Base, TimestampMixin):
    """Customer order session (dine-in or takeaway)."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'served', 'completed', 'cancelled')",
            name="check_order_status_valid",
        ),
        CheckConstraint(
            "subtotal >= 0 AND tax >= 0 AND discount >= 0 AND total >= 0",
            name="check_order_financials_non_negative",
        ),
        CheckConstraint(
            "discount <= (subtotal + tax)",
            name="check_order_discount_limit",
        ),
        CheckConstraint(
            "payment_status IN ('pending', 'paid', 'failed', 'refunded')",
            name="check_order_payment_status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    # Nullable for takeaway / counter orders; SET NULL preserves historical orders if table is deleted
    table_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("restaurant_tables.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )

    # Financial figures using Numeric(10, 2)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
        server_default="0.00",
        nullable=False,
    )
    tax: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
        server_default="0.00",
        nullable=False,
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
        server_default="0.00",
        nullable=False,
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
        server_default="0.00",
        nullable=False,
    )

    # Explicit timestamp when order is concluded (paid/settled or cancelled)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Tracks whether ingredient inventory was deducted for this order (idempotency guard)
    inventory_deducted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    # Idempotency key for QR / client submissions to prevent duplicate order placements
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True,
    )
    # Request fingerprint (SHA-256) to detect payload tampering on idempotency key reuse
    request_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # Payment lifecycle
    payment_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )

    # Relationships
    table: Mapped[Optional["RestaurantTable"]] = relationship("RestaurantTable", back_populates="orders")
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, order_number='{self.order_number}', status='{self.status}', total={self.total})>"


class OrderItem(Base, TimestampMixin):
    """Line item within an order containing a dish, quantity, and price snapshot."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_order_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="check_order_item_unit_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Menu-item deletion restricted so dishes on historical orders cannot be wiped
    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    # Crucial: price snapshot at the exact time the order was placed
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    special_instructions: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="order_items")
    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="order_items")

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, order_id={self.order_id}, menu_item_id={self.menu_item_id}, qty={self.quantity}, unit_price={self.unit_price})>"
