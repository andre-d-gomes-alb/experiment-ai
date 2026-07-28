from typing import List
from fastapi import HTTPException, status

from app.domain.experiments import can_manage_members, ExperimentMemberRoleEnum
from app.infrastructure.db.models import User, ExperimentMember
from app.infrastructure.db.repositories import (
    ExperimentMemberRepository, ExperimentRepository, UserRepository
)
from app.api.v1.experiments.members import MemberCreate, MemberRead, MemberDetailRead, MemberCreator
from app.core.enums import UserRoleEnum


ALLOWED_MEMBER_SORT_FIELDS = {
    "user_id",
    "email",
    "full_name",
    "company",
    "role",
    "is_active",
    "joined_at",
    "updated_at",
}


class ExperimentMembersService:
    def __init__(
        self,
        experiment_repo: ExperimentRepository,
        member_repo: ExperimentMemberRepository,
        user_repo: UserRepository,
    ):
        self.experiment_repo = experiment_repo
        self.member_repo = member_repo
        self.user_repo = user_repo

    async def add_member(
        self,
        *,
        experiment_id: str,
        member_data: MemberCreate,
        current_user: User,
    ) -> MemberRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )

        if not can_manage_members(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment members"
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        user = await self.user_repo.get_by_email(member_data.email)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        if user.role == UserRoleEnum.CONSUMER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add a consumer as experiment member"
            )

        if user.id == experiment.owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owner is already a member"
            )

        member = await self.member_repo.get(experiment_id, user.id)
        if member:
            if member.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already member of experiment"
                )
            member.is_active = True
            member.role = member_data.role
            member = await self.member_repo.update(member)
        else:
            member = ExperimentMember(
                experiment_id=experiment.id,
                user_id=user.id,
                role=member_data.role,
                is_active=True,
                joined_by_user_id=current_user.id,
            )
            member = await self.member_repo.create(member)

        return MemberRead.from_orm(member)

    async def list_members(
        self,
        *,
        experiment_id: str,
        current_user: User,
        include_inactive: bool = False,
        email: str | None = None,
        full_name: str | None = None,
        company: str | None = None,
        role: ExperimentMemberRoleEnum | None = None,
        sort: str = "user_id asc",
    ) -> List[MemberRead]:

        _, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )

        if not can_manage_members(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment members"
            )

        try:
            field, order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'"
            )

        if field not in ALLOWED_MEMBER_SORT_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field '{field}'"
            )

        if order not in {"asc", "desc"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sort order must be 'asc' or 'desc'"
            )

        members = await self.member_repo.search(
            experiment_id=experiment_id,
            include_inactive=include_inactive,
            email=email,
            full_name=full_name,
            company=company,
            role=role,
            sort_field=field,
            sort_order=order,
        )

        return [MemberRead.from_orm(m) for m in members]
    
    async def get_member(
        self,
        *,
        experiment_id: str,
        user_id: int,
        current_user: User,
    ) -> MemberDetailRead:
        """Get a single member with full_name and company"""
        _, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )

        if not access.is_owner and access.member_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment members"
            )

        member = await self.member_repo.get(experiment_id, user_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )

        return MemberDetailRead(
            **MemberRead.from_orm(member).dict(),
            joined_by=MemberCreator(
                user_id=member.joined_by.id,
                email=member.joined_by.email,
            ),
        )

    async def update_member_role(
        self,
        *,
        experiment_id: str,
        user_id: int,
        role: ExperimentMemberRoleEnum,
        current_user: User,
    ) -> MemberRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )

        if not can_manage_members(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment members"
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        member = await self.member_repo.get(experiment_id, user_id)
        if not member or not member.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active member not found"
            )
        user = await self.user_repo.get_by_id(user_id)
        if user.role == UserRoleEnum.CONSUMER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a consumer as experiment member"
            )

        if user_id == experiment.owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change owner role"
            )

        member.role = role
        member = await self.member_repo.update(member)

        return MemberRead.from_orm(member)

    async def deactivate_member(
        self,
        *,
        experiment_id: str,
        user_id: int,
        current_user: User,
    ) -> MemberRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )

        if not can_manage_members(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment members"
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        if user_id == experiment.owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove owner"
            )

        member = await self.member_repo.get(experiment_id, user_id)
        if not member or not member.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active member not found"
            )

        member.is_active = False
        member = await self.member_repo.update(member)

        return MemberRead.from_orm(member)
