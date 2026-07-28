from fastapi import APIRouter, Path, Depends
from typing import List

from app.infrastructure.db.models import User
from app.core.security import get_current_user
from app.application.experiments import ExperimentVariablesService
from .schemas import VariableCreate, VariableUpdate, VariableRead, VariableDetailRead
from app.api.v1.experiments import get_experiment_variables_service


router = APIRouter()


# Create variable
@router.post("/", response_model=VariableRead)
async def create_experiment_variable(
    experiment_id: str = Path(...),
    data: VariableCreate = None,
    current_user: User = Depends(get_current_user),
    service: ExperimentVariablesService = Depends(get_experiment_variables_service),
):
    return await service.create(
        experiment_id=experiment_id,
        data=data,
        current_user=current_user,
    )

# List variables
@router.get("/", response_model=List[VariableRead])
async def list_experiment_variables(
    experiment_id: str = Path(...),
    description: str | None = None,
    sort: str = "id asc",
    current_user: User = Depends(get_current_user),
    service: ExperimentVariablesService = Depends(get_experiment_variables_service),
):
    return await service.list(
        experiment_id=experiment_id,
        current_user=current_user,
        description=description,
        sort=sort,
    )

# Get variable detail
@router.get("/{variable_id}", response_model=VariableDetailRead)
async def get_experiment_variable(
    experiment_id: str = Path(...),
    variable_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentVariablesService = Depends(get_experiment_variables_service),
):
    return await service.get(
        experiment_id=experiment_id,
        variable_id=variable_id,
        current_user=current_user,
    )

# Update variable
@router.patch("/{variable_id}", response_model=VariableRead)
async def update_experiment_variable(
    experiment_id: str = Path(...),
    variable_id: str = Path(...),
    data: VariableUpdate = None,
    current_user: User = Depends(get_current_user),
    service: ExperimentVariablesService = Depends(get_experiment_variables_service),
):
    return await service.update(
        experiment_id=experiment_id,
        variable_id=variable_id,
        data=data,
        current_user=current_user,
    )

# Delete variable
@router.delete("/{variable_id}")
async def delete_experiment_variable(
    experiment_id: str = Path(...),
    variable_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentVariablesService = Depends(get_experiment_variables_service),
):
    await service.delete(
        experiment_id=experiment_id,
        variable_id=variable_id,
        current_user=current_user,
    )
    return {"detail": "Variable deleted"}
