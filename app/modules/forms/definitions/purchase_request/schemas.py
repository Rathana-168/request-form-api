import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.shared.schemas import ORMModel


class ItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    qty: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, decimal_places=2)


class PurchaseCreate(BaseModel):
    supplier: str = Field(min_length=1, max_length=150)
    items: list[ItemIn] = Field(min_length=1)


class PurchaseUpdate(BaseModel):
    supplier: str | None = Field(None, min_length=1, max_length=150)
    items: list[ItemIn] | None = Field(None, min_length=1)  # full list when sent


class ItemOut(ORMModel):
    id: uuid.UUID
    line_no: int
    description: str
    qty: int
    unit_price: Decimal


class PurchaseOut(ORMModel):
    id: uuid.UUID
    supplier: str
    total: Decimal
    items: list[ItemOut]