from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class QRTokenResponse(BaseModel):
    """Schema for QR ordering token information."""

    table_id: int
    table_number: str
    qr_token: str
    qr_url: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class QRTableInfoResponse(BaseModel):
    """Publicly visible table metadata when customer scans a QR code."""

    table_number: str
    capacity: int
    has_active_order: bool

    model_config = ConfigDict(from_attributes=True)


class QROrderItemCreate(BaseModel):
    """Schema for a single line item submitted via QR order."""

    menu_item_id: int = Field(..., gt=0, description="Database ID of the menu item")
    quantity: int = Field(default=1, gt=0, le=20, description="Quantity to order (1-20)")
    special_instructions: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional special preparation request (max 255 chars)",
    )

    @field_validator("special_instructions")
    @classmethod
    def sanitize_instructions(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            trimmed = value.strip()
            return trimmed if trimmed else None
        return None


class QROrderCreate(BaseModel):
    """Schema for submitting a dine-in or takeaway order via customer portal."""

    qr_token: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Active table QR ordering token if dine-in, or null for takeaway",
    )
    items: List[QROrderItemCreate] = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Ordered dish items (1-30 line items)",
    )
    idempotency_key: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="Client-generated unique key to prevent duplicate orders upon retry",
    )
    customer_name: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Optional guest name for personalized table service",
    )

    @field_validator("customer_name")
    @classmethod
    def sanitize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            trimmed = value.strip()
            return trimmed if trimmed else None
        return None


class QROrderItemResponse(BaseModel):
    """Schema for line items displayed on QR order confirmation."""

    menu_item_name: str
    quantity: int
    unit_price: Decimal
    special_instructions: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class QROrderResponse(BaseModel):
    """Schema returned to customer after successfully placing a QR order."""

    order_number: str
    table_number: str
    status: str
    payment_status: str = "pending"
    payment_method: Optional[str] = None
    items: List[QROrderItemResponse]
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QROrderStatusResponse(BaseModel):
    """Schema for tracking real-time order status updates via QR."""

    order_number: str
    table_number: str
    status: str
    payment_status: str = "pending"
    payment_method: Optional[str] = None
    total: Decimal
    created_at: datetime
    items: List[QROrderItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
