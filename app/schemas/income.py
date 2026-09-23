from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class IncomeBase(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    description: str = "Salário"
    source: str | None = None
    gross_amount: float = Field(default=0, ge=0)
    net_amount: float = Field(default=0, ge=0)
    received_date: date | None = None


class IncomeCreate(IncomeBase):
    pass


class IncomeUpdate(BaseModel):
    description: str | None = None
    source: str | None = None
    gross_amount: float | None = Field(default=None, ge=0)
    net_amount: float | None = Field(default=None, ge=0)
    received_date: date | None = None


class IncomeOut(IncomeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
