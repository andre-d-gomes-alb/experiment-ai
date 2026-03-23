from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List

from app.core.enums import UserRoleEnum, ExperimentUserRoleEnum


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    company: str | None = None

class UserCreate(UserBase):
    password: str
    role: UserRoleEnum

class UserRead(UserBase):
    id: int
    role: UserRoleEnum
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name: str | None = None
    company: str | None = None
    role: UserRoleEnum | None = None

class UserProfileBasicRead(UserBase):
    role: UserRoleEnum

    class Config:
        from_attributes = True

class UserExperimentRead(BaseModel):
    id: str
    name: str
    role: ExperimentUserRoleEnum

class UserProfileRead(UserProfileBasicRead):
    created_at: datetime
    updated_at: datetime
    experiments: List[UserExperimentRead]
    
    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    company: str | None = None
