from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.domain.experiments.enums import ExperimentMemberRoleEnum


class MemberCreate(BaseModel):
    email: EmailStr
    role: ExperimentMemberRoleEnum = ExperimentMemberRoleEnum.EDITOR

class MemberRoleUpdate(BaseModel):
    role: ExperimentMemberRoleEnum

class MemberRead(BaseModel):
    user_id: int
    email: EmailStr
    full_name: str | None
    company: str | None
    role: ExperimentMemberRoleEnum
    is_active: bool
    joined_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, member) -> "MemberRead":
        return cls(
            user_id=member.user_id,
            email=member.user.email,
            full_name=getattr(member.user, "full_name", None),
            company=getattr(member.user, "company", None),
            role=member.role,
            is_active=member.is_active,
            joined_at=member.joined_at,
            updated_at=member.updated_at,
        )
    
class MemberCreator(BaseModel):
    user_id: int
    email: str

class MemberDetailRead(MemberRead):
    joined_by: MemberCreator
