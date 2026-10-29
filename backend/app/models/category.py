from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.menu_item import MenuItem


class Category(Base, TimestampMixin):
    """Logical grouping for menu items (e.g., Appetizers, Main Course, Drinks)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 1:N relationship with MenuItem (deletion of category restricted if items exist)
    menu_items: Mapped[List["MenuItem"]] = relationship(
        "MenuItem",
        back_populates="category",
        cascade="save-update, merge",
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}')>"
