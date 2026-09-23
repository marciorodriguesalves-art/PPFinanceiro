from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoryOut


class FixedExpenseBase(BaseModel):
    description: str = Field(min_length=1, max_length=120)
    category_id: int | None = None
    amount: float = Field(default=0, ge=0)
    due_day: int | None = Field(default=None, ge=1, le=31)
    active: bool = True


class FixedExpenseCreate(FixedExpenseBase):
    pass


class FixedExpenseUpdate(BaseModel):
    description: str | None = None
    category_id: int | None = None
    amount: float | None = Field(default=None, ge=0)
    due_day: int | None = Field(default=None, ge=1, le=31)
    active: bool | None = None


class FixedExpenseOut(FixedExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category: CategoryOut | None = None


class PaymentMark(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    paid: bool = True
    paid_date: date | None = None
    amount_paid: float | None = Field(default=None, ge=0)


class FixedExpensePaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fixed_expense_id: int
    year: int
    month: int
    paid: bool
    paid_date: date | None
    amount_paid: float | None
