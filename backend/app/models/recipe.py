from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.menu_item import MenuItem


class Recipe(Base, TimestampMixin):
    """Recipe mapping linking a menu item to a specific required ingredient and quantity."""

    __tablename__ = "recipes"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="check_recipe_quantity_positive",
        ),
        CheckConstraint(
            "unit IN ('g', 'ml', 'each')",
            name="check_recipe_unit_valid",
        ),
        UniqueConstraint(
            "menu_item_id",
            "ingredient_id",
            name="uq_recipe_menu_item_ingredient",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="recipes")
    ingredient: Mapped["Ingredient"] = relationship("Ingredient", back_populates="recipes")

    def __repr__(self) -> str:
        return f"<Recipe(id={self.id}, menu_item_id={self.menu_item_id}, ingredient_id={self.ingredient_id}, qty={self.quantity} {self.unit})>"
