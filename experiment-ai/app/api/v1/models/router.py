from fastapi import APIRouter, Path, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional

from app.infrastructure.db.models import User
from app.core.security import get_current_user
from app.application.models import ModelService
from .schemas import (
    ModelRead, ModelDetailRead, ModelVersionRead, ModelVersionDetailRead,
    ModelVersionInferenceRequest, ModelVersionInferenceResponse,
)
from .dependencies import get_models_service


router = APIRouter()


# List Models
@router.get("/", response_model=List[ModelRead])
async def list_models(
    current_user: User = Depends(get_current_user),
    service: ModelService = Depends(get_models_service),
    tags: Optional[str] = None,
    aliases: Optional[str] = None,
    experiment_name: Optional[str] = None,
    only_experiment_models: bool = False,
    sort: str = "created_at desc",
):
    return await service.list_models(
        tags=tags,
        aliases=aliases,
        experiment_name=experiment_name,
        only_experiment_models=only_experiment_models,
        sort=sort,
    )

# Get Model
@router.get("/{name}", response_model=ModelDetailRead)
async def get_model(
    name: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ModelService = Depends(get_models_service),
):
    return await service.get_model(
        name=name
    )


# VERSIONS

# List Model Versions
@router.get("/{name}/versions", response_model=List[ModelVersionRead])
async def list_model_versions(
    name: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ModelService = Depends(get_models_service),
    tags: Optional[str] = None,
    params: Optional[str] = None,
    metrics: Optional[str] = None,
    aliases: Optional[str] = None,
    sort: str = "version desc",
):
    return await service.list_model_versions(
        name=name,
        tags=tags,
        params=params,
        metrics=metrics,
        aliases=aliases,
        sort=sort
    )

# Get Model Version
@router.get("/{name}/versions/{version}", response_model=ModelVersionDetailRead)
async def get_model_version(
    name: str = Path(...),
    version: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ModelService = Depends(get_models_service),
):
    return await service.get_model_version(
        name=name,
        version=version
    )

# Download Model Version
@router.get("/{name}/versions/{version}/download")
async def download_model_version(
    name: str = Path(...),
    version: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ModelService = Depends(get_models_service),
):
    zip_stream, filename = await service.download_model_version_zip(
        name=name,
        version=version
    )
    
    return StreamingResponse(
        zip_stream,
        media_type="application/x-zip-compressed",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/zip"
        }
    )

# Model Version Prediction
@router.post("/{name}/versions/{version}/predict", response_model=ModelVersionInferenceResponse)
async def predict_model_version(
    request: ModelVersionInferenceRequest,
    name: str = Path(...),
    version: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ModelService = Depends(get_models_service),
):
    """
    ### ⚠️ Experimental Endpoint
    This endpoint loads the model on-the-fly and clears it from memory after execution.
    Expect higher latency than production-grade endpoints.
    """

    return await service.model_version_make_prediction(
        name=name,
        version=version,
        data=request
    )
