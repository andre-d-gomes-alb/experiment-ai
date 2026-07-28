from fastapi import APIRouter, Path, Depends
from typing import List

from app.application.experiments import ExperimentMembersService
from .schemas import MemberCreate, MemberRead, MemberRoleUpdate, MemberDetailRead
from app.infrastructure.db.models import User
from app.domain.experiments import ExperimentMemberRoleEnum
from app.core.security import get_current_user
from app.api.v1.experiments import get_experiment_members_service


router = APIRouter()


# Add Experiment Member
@router.post("/", response_model=MemberRead)
async def create_experiment_member(
    experiment_id: str = Path(...),
    data: MemberCreate = None,
    current_user: User = Depends(get_current_user),
    service: ExperimentMembersService = Depends(get_experiment_members_service),
):
    return await service.add_member(
        experiment_id=experiment_id,
        current_user=current_user,
        member_data=data,
    )

# List Experiment Members
@router.get("/", response_model=List[MemberRead])
async def list_experiment_members(
    experiment_id: str = Path(...),
    email: str | None = None,
    full_name: str | None = None,
    company: str | None = None,
    role: ExperimentMemberRoleEnum | None = None,
    include_inactive: bool = False,
    sort: str = "user_id asc",
    current_user: User = Depends(get_current_user),
    service: ExperimentMembersService = Depends(get_experiment_members_service),
):
    return await service.list_members(
        experiment_id=experiment_id,
        current_user=current_user,
        include_inactive=include_inactive,
        email=email,
        full_name=full_name,
        company=company,
        role=role,
        sort=sort,
    )

# Get Experiment Member
@router.get("/{user_id}", response_model=MemberDetailRead)
async def get_experiment_member(
    experiment_id: str = Path(...),
    user_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentMembersService = Depends(get_experiment_members_service),
):
    return await service.get_member(
        experiment_id=experiment_id,
        user_id=user_id,
        current_user=current_user,
    )

# Update Experiment Member Role
@router.patch("/{user_id}", response_model=MemberRead)
async def update_experiment_member(
    experiment_id: str = Path(...),
    user_id: int = Path(...),
    data: MemberRoleUpdate = None,
    current_user: User = Depends(get_current_user),
    service: ExperimentMembersService = Depends(get_experiment_members_service),
):
    return await service.update_member_role(
        experiment_id=experiment_id,
        user_id=user_id,
        role=data.role,
        current_user=current_user,
    )

# Deactivate Experiment Member
@router.delete("/{user_id}", response_model=MemberRead)
async def deactivate_experiment_member(
    experiment_id: str = Path(...),
    user_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentMembersService = Depends(get_experiment_members_service),
):
    return await service.deactivate_member(
        experiment_id=experiment_id,
        user_id=user_id,
        current_user=current_user,
    )
