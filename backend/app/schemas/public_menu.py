from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PublicCategoryResponse(BaseModel):
    """Customer-safe category information."""
    id: int = Field(..., description="Category primary key ID")
    name: str = Field(..., description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    item_count: int = Field(0, description="Number of active menu items in this category")

    model_config = ConfigDict(from_attributes=True)


class PublicMenuItemResponse(BaseModel):
    """Customer-safe menu item information (no internal flags or audit timestamps)."""
    id: int = Field(..., description="Menu item primary key ID")
    category_id: int = Field(..., description="Category ID this item belongs to")
    category_name: Optional[str] = Field(None, description="Category name")
    name: str = Field(..., description="Menu item title")
    description: Optional[str] = Field(None, description="Detailed culinary description")
    price: Decimal = Field(..., description="Item price formatted to 2 decimal places")
    is_available: bool = Field(True, description="Item availability status")
    prep_time_minutes: Optional[int] = Field(None, description="Estimated preparation time in minutes")

    model_config = ConfigDict(from_attributes=True)


class PublicMenuResponse(BaseModel):
    """Consolidated public menu catalog containing active categories and available items."""
    categories: List[PublicCategoryResponse] = Field(..., description="Active menu categories containing items")
    items: List[PublicMenuItemResponse] = Field(..., description="All currently available menu items")
    total_categories: int = Field(..., description="Total count of active categories")
    total_items: int = Field(..., description="Total count of available menu items")
