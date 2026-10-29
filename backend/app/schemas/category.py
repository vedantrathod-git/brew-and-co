from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryBase(BaseModel):
    """Base schema with shared category attributes."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Category name (unique, 1-50 characters)",
        examples=["Appetizers"],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional category description (up to 255 characters)",
        examples=["Starters and small plates to begin your meal"],
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, value: str) -> str:
        """Ensure category name is not just whitespace."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Category name cannot be empty or only whitespace.")
        return trimmed

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: Optional[str]) -> Optional[str]:
        """Strip whitespace from description if provided."""
        if value is not None:
            trimmed = value.strip()
            return trimmed if trimmed else None
        return None


class CategoryCreate(CategoryBase):
    """Schema for creating a new category."""
    pass


class CategoryUpdate(CategoryBase):
    """Schema for updating an existing category."""
    pass


class CategoryResponse(CategoryBase):
    """Schema for category responses including database identifiers and timestamps."""

    id: int = Field(..., description="Unique category primary key ID")
    created_at: datetime = Field(..., description="Timestamp when category was created")
    updated_at: datetime = Field(..., description="Timestamp when category was last updated")

    model_config = ConfigDict(from_attributes=True)
