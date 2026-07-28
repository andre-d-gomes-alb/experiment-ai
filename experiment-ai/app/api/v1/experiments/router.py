from fastapi import APIRouter, Depends, Path, HTTPException, status
from typing import List

from app.application.experiments import ExperimentService
from .schemas import ExperimentCreate, ExperimentUpdate, ExperimentRead, ExperimentListRead
from app.infrastructure.db.models import User
from app.core.enums import UserRoleEnum, ExperimentUserRoleEnum
from app.core.security import get_current_user
from .dependencies import get_experiment_service


router = APIRouter()


# Create Experiment
@router.post("/", response_model=ExperimentListRead)
async def create_experiment(
    data: ExperimentCreate,
    current_user: User = Depends(get_current_user),
    service: ExperimentService = Depends(get_experiment_service),
):
    if current_user.role == UserRoleEnum.CONSUMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consumers cannot create experiments"
        )

    return await service.create(
        data=data,
        current_user=current_user,
    )

# List Experiments
@router.get("/", response_model=List[ExperimentListRead])
async def list_experiments(
    current_user: User = Depends(get_current_user),
    service: ExperimentService = Depends(get_experiment_service),
    name: str | None = None,
    description: str | None = None,
    tag: str | None = None,
    owner_id: int | None = None,
    user_role: ExperimentUserRoleEnum | None = None,
    include_archived: bool = False,
    sort: str = "id asc",
):
    if current_user.role == UserRoleEnum.CONSUMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consumers cannot list experiments"
        )

    return await service.list(
        current_user=current_user,
        include_archived=include_archived,
        name=name,
        description=description,
        tag=tag,
        owner_id=owner_id,
        user_role=user_role,
        sort=sort,
    )

# Get Experiment
@router.get("/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(
    experiment_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentService = Depends(get_experiment_service),
):
    if current_user.role == UserRoleEnum.CONSUMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consumers cannot view experiments"
        )

    return await service.get(
        experiment_id=experiment_id,
        current_user=current_user,
    )

# Update Experiment
@router.patch("/{experiment_id}", response_model=ExperimentListRead)
async def update_experiment(
    experiment_id: str,
    data: ExperimentUpdate,
    current_user: User = Depends(get_current_user),
    service: ExperimentService = Depends(get_experiment_service),
):
    if current_user.role == UserRoleEnum.CONSUMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consumers cannot update experiments"
        )

    return await service.update(
        experiment_id=experiment_id,
        data=data,
        current_user=current_user,
    )

# Archive Experiment
@router.delete("/{experiment_id}")
async def archive_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    service: ExperimentService = Depends(get_experiment_service),
):
    if current_user.role == UserRoleEnum.CONSUMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consumers cannot archive experiments"
        )

    await service.archive(
        experiment_id=experiment_id,
        current_user=current_user,
    )
    return {"detail": "Experiment archived"}

# Reactivate Experiment
@router.post("/{experiment_id}/reactivate")
async def reactivate_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    service: ExperimentService = Depends(get_experiment_service),
):
    if current_user.role == UserRoleEnum.CONSUMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consumers cannot reactivate experiments"
        )

    await service.reactivate(
        experiment_id=experiment_id,
        current_user=current_user,
    )
    return {"detail": "Experiment reactivated"}
