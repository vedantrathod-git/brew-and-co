from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Allowed status values matching the database check constraint ─────────
OrderStatusType = Literal["pending", "in_progress", "served", "completed", "cancelled"]

# ── Tax rate: documented default of 0% for this portfolio project ────────
# In production, this would come from settings or a database configuration table.
DEFAULT_TAX_RATE = Decimal("0.00")


# ── Order Item Schemas ───────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    """Schema for submitting a single item within a new order."""

    menu_item_id: int = Field(..., gt=0, description="ID of the menu item to order")
    quantity: int = Field(default=1, gt=0, description="Quantity to order (must be > 0)")
    special_instructions: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional special instructions (up to 255 characters)",
        examples=["No onions, extra spicy"],
    )

    @field_validator("special_instructions")
    @classmethod
    def sanitize_instructions(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            trimmed = value.strip()
            return trimmed if trimmed else None
        return None


class OrderItemResponse(BaseModel):
    """Schema for an order item in responses."""

    id: int
    order_id: int
    menu_item_id: int
    quantity: int
    unit_price: Decimal = Field(..., description="Price snapshot at the time the order was placed")
    special_instructions: Optional[str] = None
    menu_item_name: Optional[str] = Field(default=None, description="Name of the referenced menu item")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Order Schemas ────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    """Schema for creating a new order with one or more items."""

    table_id: Optional[int] = Field(
        default=None,
        description="Table ID for dine-in orders. Omit or set to null for takeaway.",
    )
    items: List[OrderItemCreate] = Field(
        ...,
        min_length=1,
        description="List of items to order (at least one required)",
    )
    discount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Discount amount (must be non-negative)",
    )

    @field_validator("discount")
    @classmethod
    def validate_discount_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0.00"):
            raise ValueError("Discount cannot be negative.")
        return value


class OrderUpdate(BaseModel):
    """Schema for updating an existing order.

    Updatable fields:
    - status: transition through the order lifecycle.
    - discount: adjust discount before order is completed.
    - table_id: reassign table (validated against active orders at target table).
    """

    status: Optional[OrderStatusType] = Field(
        default=None,
        description="New order status",
    )
    discount: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0.00"),
        description="Updated discount amount (must be non-negative)",
    )
    table_id: Optional[int] = Field(
        default=None,
        description="Reassign to a different table ID, or null for takeaway",
    )

    @model_validator(mode="after")
    def check_at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one of 'status', 'discount', or 'table_id' must be provided.")
        return self


class OrderResponse(BaseModel):
    """Schema for order responses including items, totals, and timestamps."""

    id: int
    order_number: str
    table_id: Optional[int] = None
    table_number: Optional[str] = Field(default=None, description="Human-readable table identifier")
    status: str
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    items: List[OrderItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    inventory_deducted: bool = False
    payment_status: str = "pending"
    payment_method: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
