from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentMethod
from app.schemas.category import CategoryOut


class DailyExpenseBase(BaseModel):
    expense_date: date
    category_id: int | None = None
    description: str = ""
    amount: float = Field(default=0, ge=0)
    payment_method: PaymentMethod = PaymentMethod.debito


class DailyExpenseCreate(DailyExpenseBase):
    pass


class DailyExpenseUpdate(BaseModel):
    expense_date: date | None = None
    category_id: int | None = None
    description: str | None = None
    amount: float | None = Field(default=None, ge=0)
    payment_method: PaymentMethod | None = None


class DailyExpenseOut(DailyExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category: CategoryOut | None = None
