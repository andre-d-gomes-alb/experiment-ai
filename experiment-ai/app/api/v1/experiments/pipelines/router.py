from fastapi import APIRouter, Depends, Path, Body
from typing import List, Optional

from app.infrastructure.db.models import User
from app.core.security import get_current_user
from app.application.experiments import ExperimentPipelinesService
from .schemas import (
    PipelineCreate, PipelineUpdate, PipelineReadBase, PipelineDetailReadBase,
    PipelineRead, PipelineDetailRead, PipelineReadError, PipelineDetailReadError,
    RunRead, RunDetailRead,
)
from app.api.v1.experiments import get_experiment_pipelines_service
from app.domain.experiments import (
    ExperimentPipelineStatusEnum, ExperimentPipelineRunStateEnum,
    ExperimentPipelineRunTriggeredByEnum, ExperimentPipelineRunTypeEnum,
)


router = APIRouter()


# Create Experiment Pipeline
@router.post("/", response_model=PipelineReadBase)
async def create_experiment_pipeline(
    experiment_id: str = Path(...),
    data: PipelineCreate = Body(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
):
    return await service.create(
        experiment_id=experiment_id,
        data=data,
        current_user=current_user,
    )

# List Experiment Pipelines
@router.get("/", response_model=List[PipelineRead | PipelineReadError | PipelineReadBase])
async def list_experiment_pipelines(
    experiment_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
    name: str | None = None,
    description: str | None = None,
    tag: str | None = None,
    status: ExperimentPipelineStatusEnum | None = None,
    sort: str = "id asc",
):
    return await service.list(
        experiment_id=experiment_id,
        current_user=current_user,
        name=name,
        description=description,
        tag=tag,
        p_status=status,
        sort=sort,
    )

# Get Experiment Pipeline
@router.get("/{pipeline_id}", response_model=PipelineDetailRead | PipelineDetailReadError | PipelineDetailReadBase)
async def get_experiment_pipeline(
    experiment_id: str = Path(...),
    pipeline_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
):
    return await service.get(
        experiment_id=experiment_id,
        pipeline_id=pipeline_id,
        current_user=current_user,
    )

# Update Experiment Pipeline
@router.put("/{pipeline_id}", response_model=PipelineReadBase)
async def update_experiment_pipeline(
    experiment_id: str = Path(...),
    pipeline_id: str = Path(...),
    data: PipelineUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
):
    return await service.update(
        experiment_id=experiment_id,
        pipeline_id=pipeline_id,
        data=data,
        current_user=current_user,
    )

# Delete Experiment Pipeline
@router.delete("/{pipeline_id}")
async def delete_experiment_pipeline(
    experiment_id: str = Path(...),
    pipeline_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
):
    await service.delete(
        experiment_id=experiment_id,
        pipeline_id=pipeline_id,
        current_user=current_user,
    )
    return {"detail": "Pipeline deleted"}

# Activate Experiment Pipeline
@router.post("/{pipeline_id}/activate", response_model=PipelineDetailRead)
async def activate_experiment_pipeline(
    experiment_id: str,
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
):
    return await service.activate(
        experiment_id=experiment_id,
        pipeline_id=pipeline_id,
        current_user=current_user,
    )

# Pause Experiment Pipeline
@router.post("/{pipeline_id}/pause", response_model=PipelineDetailRead)
async def pause_experiment_pipeline(
    experiment_id: str,
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
):
    return await service.pause(
        experiment_id=experiment_id,
        pipeline_id=pipeline_id,
        current_user=current_user,
    )

# RUNS

# Trigger Experiment Pipeline
@router.post("/{pipeline_id}/trigger", response_model=RunRead)
async def trigger_experiment_pipeline(
    experiment_id: str,
    pipeline_id: str,
    conf: Optional[dict] = Body(default=None),
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
):
    return await service.trigger(
        experiment_id=experiment_id,
        pipeline_id=pipeline_id,
        conf=conf,
        current_user=current_user,
    )

# List Experiment Pipeline Runs
@router.get("/{pipeline_id}/runs", response_model=List[RunRead])
async def list_experiment_pipeline_runs(
    experiment_id: str,
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
    max_runs_analysed: int = 50,
    run_type: ExperimentPipelineRunTypeEnum | None = None,
    state: ExperimentPipelineRunStateEnum | None = None,
    triggered_by: ExperimentPipelineRunTriggeredByEnum | None = None,
    sort: str = "execution_date asc",
):
    return await service.list_runs(
        experiment_id=experiment_id,
        pipeline_id=pipeline_id,
        current_user=current_user,
        max_runs_analysed=max_runs_analysed,
        run_type=run_type,
        state=state,
        triggered_by=triggered_by,
        sort=sort,
    )

# Get Experiment Pipeline Run
@router.get("/{pipeline_id}/runs/{run_id}", response_model=RunDetailRead)
async def get_experiment_pipeline_run(
    experiment_id: str,
    pipeline_id: str,
    run_id: str,
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
):
    return await service.get_run(
        experiment_id=experiment_id,
        pipeline_id=pipeline_id,
        run_id=run_id,
        current_user=current_user,
    )

# Delete Experiment Pipeline Run
@router.delete("/{pipeline_id}/runs/{run_id}")
async def delete_experiment_pipeline_run(
    experiment_id: str,
    pipeline_id: str,
    run_id: str,
    current_user: User = Depends(get_current_user),
    service: ExperimentPipelinesService = Depends(get_experiment_pipelines_service),
):
    await service.delete_run(
        experiment_id=experiment_id,
        pipeline_id=pipeline_id,
        run_id=run_id,
        current_user=current_user,
    )
    return {"detail": "Pipeline run deleted"}
