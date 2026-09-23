from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoryOut


class InstallmentBase(BaseModel):
    description: str = Field(min_length=1, max_length=160)
    category_id: int | None = None
    card: str | None = None
    installment_amount: float = Field(default=0, ge=0)
    installments_total: int = Field(default=1, ge=1, le=120)
    start_year: int = Field(ge=2000, le=2100)
    start_month: int = Field(ge=1, le=12)


class InstallmentCreate(InstallmentBase):
    pass


class InstallmentUpdate(BaseModel):
    description: str | None = None
    category_id: int | None = None
    card: str | None = None
    installment_amount: float | None = Field(default=None, ge=0)
    installments_total: int | None = Field(default=None, ge=1, le=120)
    start_year: int | None = Field(default=None, ge=2000, le=2100)
    start_month: int | None = Field(default=None, ge=1, le=12)


class InstallmentOut(InstallmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category: CategoryOut | None = None
