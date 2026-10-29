from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.order import Order
    from app.models.user import User

VALID_MOVEMENT_TYPES = (
    "initial",
    "restock",
    "manual_correction",
    "waste",
    "order_consumption",
    "order_reversal",
)


class StockMovement(Base):
    """Immutable, auditable ledger entry for every inventory stock change."""

    __tablename__ = "stock_movements"

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('initial', 'restock', 'manual_correction', 'waste', 'order_consumption', 'order_reversal')",
            name="check_stock_movement_type_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Signed decimal: positive for restock / initial / reversal; negative for consumption / waste
    quantity_delta: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    movement_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    ingredient: Mapped["Ingredient"] = relationship("Ingredient", back_populates="stock_movements")
    order: Mapped[Optional["Order"]] = relationship("Order")
    user: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<StockMovement(id={self.id}, ingredient_id={self.ingredient_id}, delta={self.quantity_delta}, type='{self.movement_type}')>"
