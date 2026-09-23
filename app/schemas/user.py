from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Role


class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    role: Role = Role.user
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
