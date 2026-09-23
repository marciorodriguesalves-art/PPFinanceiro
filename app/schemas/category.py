from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CategoryKind


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: CategoryKind = CategoryKind.variavel
    default_target_rate: float | None = Field(default=None, ge=0, le=1)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    kind: CategoryKind | None = None
    default_target_rate: float | None = Field(default=None, ge=0, le=1)


class CategoryOut(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
