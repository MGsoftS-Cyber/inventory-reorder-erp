"""Public API contracts: currency is explicit and decimal values retain precision."""

import re
from datetime import date
from typing import Literal
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# The first release implements these currencies explicitly; conversion is not implied.
SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "CHF", "JPY", "AED"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password", mode="before")
    @classmethod
    def preserve_password(cls, value):
        # Password whitespace is meaningful; reject it at the boundaries instead of silently changing it.
        if isinstance(value, str) and value != value.strip():
            raise ValueError("Password must not start or end with whitespace.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        value = value.lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


Quantity = Decimal


class SupplierInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(default="", max_length=254)


class WarehouseInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)


class ProductInput(StrictModel):
    sku: str = Field(min_length=1, max_length=40, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(default="unit", min_length=1, max_length=20)
    supplier_id: str | None = None
    unit_cost: Decimal = Field(ge=0, le=Decimal("1e9"), max_digits=18, decimal_places=4, allow_inf_nan=False)
    selling_price: Decimal = Field(ge=0, le=Decimal("1e9"), max_digits=18, decimal_places=4, allow_inf_nan=False)
    lead_days: int = Field(default=7, ge=0, le=365)
    safety_days: int = Field(default=7, ge=0, le=365)
    review_days: int = Field(default=7, ge=1, le=365)
    pack_size: int = Field(default=1, ge=1, le=100000)
    minimum_order: int = Field(default=1, ge=0, le=1000000)


class MovementInput(StrictModel):
    product_id: str
    warehouse_id: str
    quantity: Decimal = Field(gt=0, le=Decimal("1e9"), max_digits=18, decimal_places=4, allow_inf_nan=False)
    kind: Literal["receipt", "sale", "issue", "adjustment_in", "adjustment_out", "transfer"]
    destination_id: str | None = None
    note: str = Field(min_length=1, max_length=500)


class PurchaseItemInput(StrictModel):
    product_id: str
    quantity: Decimal = Field(gt=0, le=Decimal("1e9"), max_digits=18, decimal_places=4, allow_inf_nan=False)
    unit_cost: Decimal = Field(ge=0, le=Decimal("1e9"), max_digits=18, decimal_places=4, allow_inf_nan=False)


class PurchaseInput(StrictModel):
    supplier_id: str
    warehouse_id: str
    expected_date: date
    currency: Literal["USD"] = "USD"
    lines: list[PurchaseItemInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_lines(self):
        if self.expected_date < date.today():
            raise ValueError("Expected delivery cannot be in the past.")
        if len({x.product_id for x in self.lines}) != len(self.lines):
            raise ValueError("Each product may appear once per purchase order.")
        return self


class ReceiveItem(StrictModel):
    line_id: str
    quantity: Decimal = Field(gt=0, le=Decimal("1e9"), max_digits=18, decimal_places=4, allow_inf_nan=False)


class ReceiveInput(StrictModel):
    lines: list[ReceiveItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_lines(self):
        if len({x.line_id for x in self.lines}) != len(self.lines):
            raise ValueError("Receive each order line at most once in a request.")
        return self


class AnalysisInput(StrictModel):
    warehouse_id: str
    lookback_days: int = Field(default=90, ge=7, le=730)
    slow_days: int = Field(default=30, ge=1, le=730)


class CsvInput(StrictModel):
    csv_text: str = Field(min_length=1, max_length=500000)


class ApplyDemandInput(CsvInput):
    warehouse_id: str
