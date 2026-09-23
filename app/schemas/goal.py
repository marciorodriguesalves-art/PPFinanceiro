from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.category import CategoryOut


class GoalBase(BaseModel):
    category_id: int
    year: int = Field(default=0, ge=0, le=2100)
    month: int = Field(default=0, ge=0, le=12)
    target_rate: float | None = Field(default=None, ge=0, le=1)
    target_amount: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _at_least_one_target(self):
        if self.target_rate is None and self.target_amount is None:
            raise ValueError("Informe target_rate e/ou target_amount")
        return self


class GoalCreate(GoalBase):
    pass


class GoalUpdate(BaseModel):
    year: int | None = Field(default=None, ge=0, le=2100)
    month: int | None = Field(default=None, ge=0, le=12)
    target_rate: float | None = Field(default=None, ge=0, le=1)
    target_amount: float | None = Field(default=None, ge=0)


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category_id: int
    year: int
    month: int
    target_rate: float | None
    target_amount: float | None
    category: CategoryOut | None = None
