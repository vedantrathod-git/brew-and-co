from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.order import OrderItem
    from app.models.recipe import Recipe


class MenuItem(Base, TimestampMixin):
    """Dishes, drinks, or other items offered on the restaurant menu."""

    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("price >= 0", name="check_menu_item_price_non_negative"),
        CheckConstraint("prep_time_minutes >= 0", name="check_menu_item_prep_time_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    prep_time_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=15,
        server_default="15",
        nullable=True,
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="menu_items")
    # Menu-item deletion restricted when referenced by historical order_items
    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="menu_item")
    recipes: Mapped[List["Recipe"]] = relationship("Recipe", back_populates="menu_item", cascade="all, delete-orphan")

    @property
    def category_name(self) -> Optional[str]:
        """Convenience property returning associated category name when loaded."""
        return self.category.name if self.category else None

    def __repr__(self) -> str:
        return f"<MenuItem(id={self.id}, name='{self.name}', price={self.price})>"
