from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.expense import ExpenseCategory


class ExpenseBase(BaseModel):
    name: str
    category: ExpenseCategory
    value: Decimal


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    name: str | None = None
    category: ExpenseCategory | None = None
    value: Decimal | None = None


class ExpenseResponse(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    created_at: dt.datetime
