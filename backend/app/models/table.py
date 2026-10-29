from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class RestaurantTable(Base, TimestampMixin):
    """Physical dining tables inside the restaurant."""

    __tablename__ = "restaurant_tables"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="check_table_capacity_positive"),
        CheckConstraint(
            "status IN ('available', 'occupied', 'reserved')",
            name="check_table_status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=4, server_default="4", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="available",
        server_default="available",
        nullable=False,
    )

    # Secure QR ordering token and generation timestamp
    qr_token: Mapped[Optional[str]] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True,
    )
    qr_token_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 1:N relationship with Order (database handles ON DELETE SET NULL)
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        back_populates="table",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<RestaurantTable(id={self.id}, table_number='{self.table_number}', status='{self.status}')>"
