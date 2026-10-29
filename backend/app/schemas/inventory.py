from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

IngredientUnit = Literal["g", "ml", "each"]
MovementType = Literal["initial", "restock", "manual_correction", "waste", "order_consumption", "order_reversal"]
AdjustmentType = Literal["restock", "waste", "manual_correction"]


# ── Ingredient Schemas ───────────────────────────────────────────────────

class IngredientBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Unique ingredient name")
    description: Optional[str] = Field(default=None, description="Culinary or storage notes")
    unit: IngredientUnit = Field(..., description="Base measurement unit: 'g', 'ml', or 'each'")
    minimum_stock: Decimal = Field(default=Decimal("0.000"), ge=Decimal("0.000"), description="Safety reorder threshold")
    unit_cost: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"), description="Cost per base unit in USD")

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Ingredient name cannot be blank.")
        return trimmed


class IngredientCreate(IngredientBase):
    initial_stock: Decimal = Field(default=Decimal("0.000"), ge=Decimal("0.000"), description="Initial quantity on hand")


class IngredientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = None
    unit: Optional[IngredientUnit] = None
    minimum_stock: Optional[Decimal] = Field(default=None, ge=Decimal("0.000"))
    unit_cost: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"))
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Ingredient name cannot be blank.")
            return trimmed
        return None


class IngredientResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    current_stock: Decimal
    unit: str
    minimum_stock: Decimal
    unit_cost: Optional[Decimal] = None
    is_active: bool
    stock_status: str  # 'in_stock', 'low_stock', 'out_of_stock'
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IngredientStockAdjustment(BaseModel):
    """Schema for manual adjustments (restock delivery, waste, correction)."""
    adjustment_type: AdjustmentType = Field(..., description="'restock' (adds stock), 'waste' (reduces stock), or 'manual_correction'")
    quantity: Decimal = Field(..., gt=Decimal("0.000"), description="Absolute quantity to adjust (always positive in payload)")
    reason: Optional[str] = Field(default=None, max_length=255, description="Auditable justification (e.g., 'Vendor delivery #1042', 'Spilled milk batch')")


# ── Recipe Schemas ───────────────────────────────────────────────────────

class RecipeItemCreate(BaseModel):
    menu_item_id: int = Field(..., gt=0, description="Target menu item ID")
    ingredient_id: int = Field(..., gt=0, description="Required ingredient ID")
    quantity: Decimal = Field(..., gt=Decimal("0.000"), description="Quantity consumed per menu item prepared")
    unit: IngredientUnit = Field(..., description="Measurement unit (must match ingredient unit)")


class RecipeItemUpdate(BaseModel):
    quantity: Decimal = Field(..., gt=Decimal("0.000"), description="Updated quantity consumed per menu item")
    unit: Optional[IngredientUnit] = None


class RecipeItemResponse(BaseModel):
    id: int
    menu_item_id: int
    menu_item_name: Optional[str] = None
    ingredient_id: int
    ingredient_name: Optional[str] = None
    ingredient_unit: Optional[str] = None
    quantity: Decimal
    unit: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MenuItemRecipeResponse(BaseModel):
    menu_item_id: int
    menu_item_name: str
    category_name: Optional[str] = None
    has_recipe: bool
    recipe_items: List[RecipeItemResponse] = []


# ── Stock Movement Schemas ───────────────────────────────────────────────

class StockMovementResponse(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: Optional[str] = None
    ingredient_unit: Optional[str] = None
    quantity_delta: Decimal
    movement_type: str
    reason: Optional[str] = None
    order_id: Optional[int] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Dashboard Summary Schema ─────────────────────────────────────────────

class InventorySummaryResponse(BaseModel):
    total_active_ingredients: int
    low_stock_count: int
    out_of_stock_count: int
    total_movements_recorded: int
