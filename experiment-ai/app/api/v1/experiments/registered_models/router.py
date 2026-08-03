from fastapi import APIRouter, Path, Depends, Body
from fastapi.responses import StreamingResponse
from typing import List, Optional

from app.infrastructure.db.models import User
from app.core.security import get_current_user
from app.application.experiments import ExperimentRegisteredModelsService
from .schemas import (
    RegisteredModelRead, RegisteredModelDetailRead, RegisteredModelUpdate,
    RegisteredModelVersionRead, RegisteredModelVersionUpdate, RegisteredModelVersionDetailRead,
    RegisteredModelVersionPromote, RegisteredModelVersionPromoteRead,
)
from app.api.v1.experiments import get_experiment_registered_models_service


router = APIRouter()


# List Registered Models
@router.get("/", response_model=List[RegisteredModelRead])
async def list_experiment_registered_models(
    experiment_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
    tags: Optional[str] = None,
    aliases: Optional[str] = None,
    is_private: Optional[bool] = None,
    sort: str = "created_at desc",
):
    return await service.list_registered_models(
        experiment_id=experiment_id,
        current_user=current_user,
        tags=tags,
        aliases=aliases,
        is_private=is_private,
        sort=sort,
    )

# Get Registered Model
@router.get("/{name}", response_model=RegisteredModelDetailRead)
async def get_experiment_registered_model(
    experiment_id: str = Path(...),
    name: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
):
    return await service.get_registered_model(
        experiment_id=experiment_id,
        name=name,
        current_user=current_user
    )

# Update Registered Model
@router.patch("/{name}", response_model=RegisteredModelRead)
async def update_experiment_registered_model(
    experiment_id: str = Path(...),
    name: str = Path(...),
    obj_in: RegisteredModelUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
):
    return await service.update_registered_model(
        experiment_id=experiment_id,
        name=name,
        obj_in=obj_in,
        current_user=current_user
    )

# Delete Registered Model
@router.delete("/{name}")
async def delete_experiment_registered_model(
    experiment_id: str = Path(...),
    name: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
):
    await service.delete_registered_model(
        experiment_id=experiment_id,
        name=name,
        current_user=current_user
    )

    return {"detail": "Registered model deleted"}


# VERSIONS

# List Registered Model Versions
@router.get("/{name}/versions", response_model=List[RegisteredModelVersionRead])
async def list_experiment_registered_model_versions(
    experiment_id: str = Path(...),
    name: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
    run_id: Optional[str] = None,
    model_id: Optional[str] = None,
    tags: Optional[str] = None,
    params: Optional[str] = None,
    metrics: Optional[str] = None,
    aliases: Optional[str] = None,
    is_ready: Optional[bool] = None,
    sort: str = "version desc",
):
    return await service.list_registered_model_versions(
        experiment_id=experiment_id,
        name=name,
        current_user=current_user,
        run_id=run_id,
        model_id=model_id,
        tags=tags,
        params=params,
        metrics=metrics,
        aliases=aliases,
        is_ready=is_ready,
        sort=sort
    )

# Get Registered Model Version
@router.get("/{name}/versions/{version}", response_model=RegisteredModelVersionDetailRead)
async def get_experiment_registered_model_version(
    experiment_id: str = Path(...),
    name: str = Path(...),
    version: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
):
    return await service.get_registered_model_version(
        experiment_id=experiment_id,
        name=name,
        version=version,
        current_user=current_user
    )

# Update Registered Model Version
@router.patch("/{name}/versions/{version}", response_model=RegisteredModelVersionRead)
async def update_experiment_registered_model_version(
    experiment_id: str = Path(...),
    name: str = Path(...),
    version: str = Path(...),
    obj_in: RegisteredModelVersionUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
):
    return await service.update_registered_model_version(
        experiment_id=experiment_id,
        name=name,
        version=version,
        obj_in=obj_in,
        current_user=current_user
    )

# Delete Registered Model Version
@router.delete("/{name}/versions/{version}")
async def delete_experiment_registered_model_version(
    experiment_id: str = Path(...),
    name: str = Path(...),
    version: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
):
    await service.delete_registered_model_version(
        experiment_id=experiment_id,
        name=name,
        version=version,
        current_user=current_user,
    )

    return {"detail": "Registered model version deleted"}

# Download Registered Model Version
@router.get("/{name}/versions/{version}/download")
async def download_experiment_registered_model_version(
    experiment_id: str = Path(...),
    name: str = Path(...),
    version: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
):
    zip_stream, filename = await service.download_registered_model_version_zip(
        experiment_id=experiment_id,
        name=name,
        version=version,
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

# Promote Registered Model Version (copy version)
@router.post("/{name}/versions/{version}/promote", response_model=RegisteredModelVersionPromoteRead)
async def promote_experiment_registered_model_version(
    experiment_id: str = Path(...),
    name: str = Path(...),
    version: str = Path(...),
    target: RegisteredModelVersionPromote = Body(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRegisteredModelsService = Depends(get_experiment_registered_models_service),
):
    return await service.promote_registered_model_version(
        experiment_id=experiment_id,
        name=name,
        version=version,
        target=target,
        current_user=current_user
    )
