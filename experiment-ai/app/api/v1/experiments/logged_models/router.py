from fastapi import APIRouter, Path, Depends, Body
from fastapi.responses import StreamingResponse
from typing import List, Optional

from app.infrastructure.db.models import User
from app.core.security import get_current_user
from app.application.experiments import ExperimentLoggedModelsService
from app.domain.experiments import ExperimentLoggedModelStatusEnum
from .schemas import (
    LoggedModelRead, LoggedModelDetailRead, LoggedModelUpdate, LoggedModelRegister, LoggedModelRegisterRead,
)
from app.api.v1.experiments import get_experiment_logged_models_service


router = APIRouter()


# List Experiment Logged Models
@router.get("/", response_model=List[LoggedModelRead])
async def list_experiment_logged_models(
    experiment_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentLoggedModelsService = Depends(get_experiment_logged_models_service),
    name: Optional[str] = None,
    run_id: Optional[str] = None,
    tags: Optional[str] = None,
    params: Optional[str] = None,
    metrics: Optional[str] = None,
    has_registered: Optional[bool] = None,
    status: ExperimentLoggedModelStatusEnum = ExperimentLoggedModelStatusEnum.READY,
    sort: str = "created_at desc",
):
    return await service.list_logged_models(
        experiment_id=experiment_id,
        current_user=current_user,
        name=name,
        run_id=run_id,
        tags=tags,
        params=params,
        metrics=metrics,
        has_registered=has_registered,
        m_status=status,
        sort=sort,
    )

# Get Experiment Logged Model
@router.get("/{model_id}", response_model=LoggedModelDetailRead)
async def get_experiment_logged_model(
    experiment_id: str = Path(...),
    model_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentLoggedModelsService = Depends(get_experiment_logged_models_service),
):
    return await service.get_logged_model(
        experiment_id=experiment_id,
        model_id=model_id,
        current_user=current_user,
    )

# Update Experiment Logged Model
@router.patch("/{model_id}", response_model=LoggedModelRead)
async def update_experiment_logged_model(
    experiment_id: str = Path(...),
    model_id: str = Path(...),
    obj_in: LoggedModelUpdate = None,
    current_user: User = Depends(get_current_user),
    service: ExperimentLoggedModelsService = Depends(get_experiment_logged_models_service),
):
    return await service.update_logged_model(
        experiment_id=experiment_id,
        model_id=model_id,
        obj_in=obj_in,
        current_user=current_user,
    )

# Delete Experiment Logged Model
@router.delete("/{model_id}")
async def delete_experiment_logged_model(
    experiment_id: str = Path(...),
    model_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentLoggedModelsService = Depends(get_experiment_logged_models_service),
):
    await service.delete_logged_model(
        experiment_id=experiment_id,
        model_id=model_id,
        current_user=current_user,
    )
    return {"detail": "Logged model deleted"}

# Download Experiment Logged Model
@router.get("/{model_id}/download")
async def download_experiment_logged_model(
    experiment_id: str = Path(...),
    model_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentLoggedModelsService = Depends(get_experiment_logged_models_service),
):
    zip_stream, filename = await service.download_model_zip(
        experiment_id=experiment_id,
        model_id=model_id,
        current_user=current_user
    )
    
    return StreamingResponse(
        zip_stream,
        media_type="application/x-zip-compressed",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/zip"
        }
    )

# Register Experiment Logged Model
@router.post("/{model_id}/register", response_model=LoggedModelRegisterRead)
async def register_experiment_logged_model(
    experiment_id: str = Path(...),
    model_id: str = Path(...),
    obj_in: LoggedModelRegister = Body(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentLoggedModelsService = Depends(get_experiment_logged_models_service),
):
    return await service.register_logged_model(
        experiment_id=experiment_id,
        model_id=model_id,
        obj_in=obj_in,
        current_user=current_user
    )
