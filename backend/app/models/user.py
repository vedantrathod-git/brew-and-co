from typing import Optional
from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# Supported system roles
VALID_ROLES = ("admin", "manager", "cashier", "kitchen")


class User(Base, TimestampMixin):
    """User account model for authentication and role-based access control (RBAC)."""

    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'manager', 'cashier', 'kitchen')",
            name="check_user_role_valid",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        server_default="cashier",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default="true",
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}', is_active={self.is_active})>"
