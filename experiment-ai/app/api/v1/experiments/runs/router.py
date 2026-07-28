from fastapi import APIRouter, Path, Depends
from fastapi.responses import StreamingResponse
from typing import List

from app.infrastructure.db.models import User
from app.core.security import get_current_user
from app.application.experiments import ExperimentRunsService
from .schemas import RunRead, RunDetailRead
from app.api.v1.experiments import get_experiment_runs_service
from app.domain.experiments import ExperimentRunStatusEnum


router = APIRouter()


# List Experiment Runs
@router.get("/", response_model=List[RunRead])
async def list_experiment_runs(
    experiment_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRunsService = Depends(get_experiment_runs_service),
    run_name: str | None = None,
    status: ExperimentRunStatusEnum | None = None,
    metrics: str | None = None,
    has_models: bool | None = None,
    include_deleted: bool = False,
    sort: str = "start_time desc",
):
    return await service.list(
        experiment_id=experiment_id,
        current_user=current_user,
        run_name=run_name,
        r_status=status,
        metrics=metrics,
        has_models=has_models,
        include_deleted=include_deleted,
        sort=sort,
    )

# Get Experiment Run
@router.get("/{run_id}", response_model=RunDetailRead)
async def get_experiment_run(
    experiment_id: str = Path(...),
    run_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRunsService = Depends(get_experiment_runs_service),
):
    return await service.get(
        experiment_id=experiment_id,
        run_id=run_id,
        current_user=current_user,
    )

# Delete Experiment Run (soft delete in MLflow)
@router.delete("/{run_id}")
async def delete_experiment_run(
    experiment_id: str = Path(...),
    run_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRunsService = Depends(get_experiment_runs_service),
):
    await service.delete(
        experiment_id=experiment_id,
        run_id=run_id,
        current_user=current_user,
    )
    return {"detail": "Run deleted"}

# Download Artifacts by Run ID
@router.get("/{run_id}/download-artifacts")
async def download_experiment_run_artifacts(
    experiment_id: str = Path(...),
    run_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentRunsService = Depends(get_experiment_runs_service),
):
    zip_stream, filename = await service.download_artifacts_zip(
        experiment_id=experiment_id,
        run_id=run_id,
        current_user=current_user
    )
    
    return StreamingResponse(
        zip_stream,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
