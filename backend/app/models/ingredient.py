from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.recipe import Recipe
    from app.models.stock_movement import StockMovement

VALID_UNITS = ("g", "ml", "each")


class Ingredient(Base, TimestampMixin):
    """Raw café supply or ingredient used in recipes (e.g., coffee beans, milk, flour)."""

    __tablename__ = "ingredients"

    __table_args__ = (
        CheckConstraint(
            "current_stock >= 0",
            name="check_ingredient_current_stock_non_negative",
        ),
        CheckConstraint(
            "minimum_stock >= 0",
            name="check_ingredient_minimum_stock_non_negative",
        ),
        CheckConstraint(
            "unit IN ('g', 'ml', 'each')",
            name="check_ingredient_unit_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Stock balances stored with 3-decimal precision (e.g., 250.500 g or 1000.000 ml)
    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        default=Decimal("0.000"),
        server_default="0.000",
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # 'g', 'ml', 'each'
    minimum_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        default=Decimal("0.000"),
        server_default="0.000",
        nullable=False,
    )
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    # Relationships
    recipes: Mapped[List["Recipe"]] = relationship("Recipe", back_populates="ingredient")
    stock_movements: Mapped[List["StockMovement"]] = relationship("StockMovement", back_populates="ingredient")

    @property
    def stock_status(self) -> str:
        """Dynamic stock status: 'out_of_stock', 'low_stock', or 'in_stock'."""
        if self.current_stock <= Decimal("0.000"):
            return "out_of_stock"
        if self.current_stock <= self.minimum_stock:
            return "low_stock"
        return "in_stock"

    def __repr__(self) -> str:
        return f"<Ingredient(id={self.id}, name='{self.name}', stock={self.current_stock} {self.unit})>"
