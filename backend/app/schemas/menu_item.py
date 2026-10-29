from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MenuItemBase(BaseModel):
    """Base schema with shared menu item attributes."""

    category_id: int = Field(
        ...,
        gt=0,
        description="ID of the category this menu item belongs to",
        examples=[1],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Menu item name (unique, 1-100 characters)",
        examples=["Margherita Pizza"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional detailed description or ingredients list",
        examples=["Fresh tomato sauce, fresh mozzarella, and basil"],
    )
    price: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        decimal_places=2,
        description="Price in local currency (must be non-negative)",
        examples=[Decimal("12.50")],
    )
    is_available: bool = Field(
        default=True,
        description="Availability status (set False if out of stock)",
        examples=[True],
    )
    prep_time_minutes: Optional[int] = Field(
        default=15,
        ge=0,
        description="Estimated kitchen preparation time in minutes",
        examples=[15],
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, value: str) -> str:
        """Ensure menu item name is not blank or whitespace-only."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Menu item name cannot be empty or only whitespace.")
        return trimmed

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: Optional[str]) -> Optional[str]:
        """Strip whitespace from description if provided."""
        if value is not None:
            trimmed = value.strip()
            return trimmed if trimmed else None
        return None

    @field_validator("price")
    @classmethod
    def validate_price_non_negative(cls, value: Decimal) -> Decimal:
        """Ensure price is strictly non-negative."""
        if value < Decimal("0.00"):
            raise ValueError("Price cannot be negative.")
        return value

    @field_validator("prep_time_minutes")
    @classmethod
    def validate_prep_time_non_negative(cls, value: Optional[int]) -> Optional[int]:
        """Ensure preparation time is non-negative when provided."""
        if value is not None and value < 0:
            raise ValueError("Preparation time cannot be negative.")
        return value


class MenuItemCreate(MenuItemBase):
    """Schema for creating a new menu item."""
    pass


class MenuItemUpdate(MenuItemBase):
    """Schema for updating an existing menu item."""
    pass


class MenuItemResponse(MenuItemBase):
    """Schema for menu item responses including identifiers, timestamps, and category name."""

    id: int = Field(..., description="Unique menu item primary key ID")
    created_at: datetime = Field(..., description="Timestamp when menu item was created")
    updated_at: datetime = Field(..., description="Timestamp when menu item was last updated")
    category_name: Optional[str] = Field(
        default=None,
        description="Human-readable category name associated with this item",
        examples=["Main Course"],
    )

    model_config = ConfigDict(from_attributes=True)
