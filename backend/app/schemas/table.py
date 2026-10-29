from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Allowed table status values matching the database check constraint
TableStatusType = Literal["available", "occupied", "reserved"]


class TableBase(BaseModel):
    """Base schema with shared table attributes."""

    table_number: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Unique table identifier (1-20 characters)",
        examples=["T1", "Table 4", "Patio-1"],
    )
    capacity: int = Field(
        default=4,
        gt=0,
        description="Seating capacity (must be greater than 0)",
        examples=[4],
    )
    status: TableStatusType = Field(
        default="available",
        description="Table occupancy status: 'available', 'occupied', or 'reserved'",
        examples=["available"],
    )

    @field_validator("table_number")
    @classmethod
    def validate_table_number_not_blank(cls, value: str) -> str:
        """Ensure table number is not empty or whitespace-only."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Table number cannot be empty or only whitespace.")
        return trimmed

    @field_validator("capacity")
    @classmethod
    def validate_capacity_positive(cls, value: int) -> int:
        """Ensure capacity is strictly greater than 0."""
        if value <= 0:
            raise ValueError("Table capacity must be greater than 0.")
        return value


class TableCreate(TableBase):
    """Schema for creating a new restaurant table."""
    pass


class TableUpdate(TableBase):
    """Schema for updating an existing restaurant table."""
    pass


class TableResponse(TableBase):
    """Schema for table responses including identifiers and timestamps."""

    id: int = Field(..., description="Unique table primary key ID")
    qr_token: Optional[str] = Field(default=None, description="Active QR ordering token if generated")
    qr_token_created_at: Optional[datetime] = Field(default=None, description="Timestamp when QR token was generated")
    created_at: datetime = Field(..., description="Timestamp when table was created")
    updated_at: datetime = Field(..., description="Timestamp when table was last updated")

    model_config = ConfigDict(from_attributes=True)
