from typing import List, Optional, Dict
from fastapi import HTTPException, status
import base64
import os
import binascii
from datetime import datetime
from croniter import croniter

from app.infrastructure.db.models import User, ExperimentPipeline
from app.infrastructure.db.repositories import ExperimentRepository, ExperimentPipelineRepository
from app.infrastructure.airflow import AirflowPipelines, AirflowPipelineRuns, AirflowDagFileWriter
from app.infrastructure.mlflow import MlflowExperimentRegisteredModelService
from app.domain.experiments import (
    can_view_experiment, can_edit_experiment,
    ExperimentPipelineStatusEnum, ExperimentPipelineRunStateEnum,
    ExperimentPipelineRunTriggeredByEnum, ExperimentPipelineRunTypeEnum,
    PipelineValidationError, validate_pipeline_code, extract_registered_model_names_pipeline_code,
)
from app.core.resource_keys import experiment_resource_key, experiment_resource_prefix
from app.api.v1.experiments.pipelines import (
    PipelineCreate, PipelineUpdate, PipelineReadBase, PipelineDetailReadBase,
    PipelineRead, PipelineDetailRead, PipelineReadError, PipelineDetailReadError, PipelineCreator,
    PipelineParams, PipelineAssets, PipelineSchedule, RunRead, RunDetailRead, TaskInstanceRead, TaskErrorRead,
)
from .reconcile import reconcile_experiment_pipelines, reconcile_experiment_pipeline


ALLOWED_SORT_FIELDS = {
    "id",
    "name",
    "description",
    "status",
    "next_run",
    "paused_at",
    "created_at",
    "updated_at",
}

ALLOWED_RUN_SORT_FIELDS = {
        "id",
        "run_type",
        "state",
        "triggered_by",
        "execution_date",
        "duration",
    }


class ExperimentPipelinesService:
    def __init__(
        self,
        experiment_repo: ExperimentRepository,
        pipeline_repo: ExperimentPipelineRepository,
        airflow_pipelines: AirflowPipelines,
        airflow_runs: AirflowPipelineRuns,
        mlflow_registered_models: MlflowExperimentRegisteredModelService,
    ):
        self.experiment_repo = experiment_repo
        self.pipeline_repo = pipeline_repo
        self.airflow_pipelines = airflow_pipelines
        self.airflow_runs = airflow_runs
        self.mlflow_registered_models = mlflow_registered_models

    async def create(
        self,
        *,
        experiment_id: str,
        data: PipelineCreate,
        current_user: User,
    ) -> PipelineReadBase:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment pipelines",
            )
        
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified",
            )
        
        # Reconcile pipelines
        pipelines_db = await reconcile_experiment_pipelines(
            experiment_id=experiment_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo,
        )
        if any(c.id == data.id for c in pipelines_db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pipeline already exists",
            )

        dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=data.id,
        )

        if await self.airflow_pipelines.get(dag_id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                   "A pipeline with this id was recently deleted and is still "
                    "being removed from Airflow. Please try again shortly."
                ),
            )
        
        prefix = experiment_resource_prefix(experiment_id)
        pipeline_ids = [prefix + d.id for d in pipelines_db]
        schedule = data.schedule
        if schedule and schedule.type != "assets":
            schedule = self._check_schedule(schedule)
        else:
            assets = await self.airflow_pipelines.get_assets(pipeline_ids)
            schedule = self._check_schedule(schedule, assets)

        params = self._check_params(data.params)

        code = None
        try:
            code = base64.b64decode(data.code_base64).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid base64 code. Please provide a valid base64-encoded UTF-8 string.",
            )
        try:
            validate_pipeline_code(code, prefix)

            rm_names = extract_registered_model_names_pipeline_code(code)
            for name in rm_names:
                await self._check_model_ownership(name, experiment.mlflow_experiment_id)
        except PipelineValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            )
        
        writer = AirflowDagFileWriter()
        writer.write_pipeline(
            pipeline_id=dag_id,
            context={
                "mlflow_experiment_id": experiment.mlflow_experiment_id,
                "dag_id": dag_id,
                "name": data.name,
                "description": data.description,
                "schedule": schedule,
                "start_date": data.start_date,
                "end_date": data.end_date,
                "catchup": data.catchup,
                "default_args": data.default_args,
                "max_active_runs": data.max_active_runs,
                "dagrun_timeout_seconds": data.dagrun_timeout_seconds,
                "tags": data.tags,
                "params": params,
                "code": code,
            },
        )

        pipeline = ExperimentPipeline(
            experiment_id=experiment_id,
            id=data.id,
            name=data.name,
            description=data.description,
            created_by_user_id=current_user.id,
            status=ExperimentPipelineStatusEnum.CREATING,
        )
        await self.pipeline_repo.create(pipeline)

        return PipelineReadBase(
            id=pipeline.id,
            name=pipeline.name,
            description=pipeline.description,
            status=pipeline.status,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
            paused_at=pipeline.paused_at,
        )

    async def list(
        self,
        *,
        experiment_id: str,
        current_user: User,
        name: str | None = None,
        description: str | None = None,
        tag: str | None = None,
        p_status: ExperimentPipelineStatusEnum | None = None,
        sort: str = "id asc",
    ) -> List[PipelineRead | PipelineReadError | PipelineReadBase]:
        _, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment pipelines",
            )
        
        try:
            sort_field, sort_order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'",
            )

        if sort_field not in ALLOWED_SORT_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field '{sort_field}'",
            )

        if sort_order not in {"asc", "desc"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sort order must be 'asc' or 'desc'",
            )
        
        # Reconcile pipelines
        await reconcile_experiment_pipelines(
            experiment_id=experiment_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo,
        )

        DB_FIELDS = {"id", "name", "description", "status", "paused_at", "created_at", "updated_at"}
        repo_sort_field = sort_field if sort_field in DB_FIELDS else "id"
        repo_sort_order = sort_order if sort_field in DB_FIELDS else "asc"

        pipelines_db = await self.pipeline_repo.list(
            experiment_id=experiment_id,
            name=name,
            description=description,
            p_status=p_status,
            sort_field=repo_sort_field,
            sort_order=repo_sort_order,
        )

        prefix = experiment_resource_prefix(experiment_id)
        airflow_dags = await self.airflow_pipelines.list(
            pipeline_id_pattern=f"{prefix}%"
        )
        af_map = {d["dag_id"].replace(prefix, "", 1): d for d in airflow_dags}

        import_errors = await self.airflow_pipelines.list_import_errors()
        error_map: dict[str, list] = {}

        for err in import_errors:
            filename_full = err.get("filename")
            if not filename_full:
                continue
                
            filename = os.path.basename(filename_full)
            if not filename.startswith(prefix) or not filename.endswith(".py"):
                continue

            dag_id = os.path.basename(filename).removesuffix(".py")
            pipeline_id = dag_id.replace(prefix, "", 1)
            error_map.setdefault(pipeline_id, []).append(err)

        result: List[PipelineRead | PipelineReadError | PipelineReadBase] = []
        for db in pipelines_db:
            af = af_map.get(db.id)
            errors = error_map.get(db.id)

            if errors:
                result.append(self._to_read_error(db, errors))

            elif af:
                result.append(self._to_read(db, af))

            else:
                result.append(PipelineReadBase(
                    id=db.id,
                    name=db.name,
                    description=db.description,
                    status=db.status,
                    created_at=db.created_at,
                    updated_at=db.updated_at,
                    paused_at=db.paused_at,
                ))

        filtered = []
        for p in result:
            if p_status and p.status != p_status:
                continue

            if tag:
                tags = getattr(p, "tags", []) or []
                if tag not in tags:
                    continue

            filtered.append(p)

        def sort_key(obj):
            value = getattr(obj, sort_field, None)
            return (value is None, value)

        filtered.sort(
            key=sort_key,
            reverse=(sort_order == "desc")
        )

        return filtered

    async def get(
        self,
        *,
        experiment_id: str,
        pipeline_id: str,
        current_user: User,
    ) -> PipelineDetailRead | PipelineDetailReadError | PipelineDetailReadBase:
        _, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment pipelines",
            )

        # Reconcile pipeline
        pipeline = await reconcile_experiment_pipeline(
            experiment_id=experiment_id,
            id=pipeline_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        
        af_dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=pipeline_id,
        )

        import_errors = await self.airflow_pipelines.list_import_errors()
        errors = [
            e for e in import_errors
            if os.path.basename(e.get("filename", "")) == f"{af_dag_id}.py"
        ]

        af = await self.airflow_pipelines.get(af_dag_id)

        if errors:
            return self._to_detail_error(pipeline, errors)

        if af:
            assets = await self.airflow_pipelines.get_assets([af_dag_id])  
            return self._to_detail(pipeline, af, assets)

        return PipelineDetailReadBase(
            id=pipeline.id,
            name=pipeline.name,
            description=pipeline.description,
            status=pipeline.status,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
            paused_at=pipeline.paused_at,
            created_by=PipelineCreator(
                user_id=pipeline.created_by.id,
                email=pipeline.created_by.email,
            ),
        )

    async def update(
        self,
        *,
        experiment_id: str,
        pipeline_id: str,
        data: PipelineUpdate,
        current_user: User,
    ) -> PipelineReadBase:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment pipelines"
            )

        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        # Reconcile pipelines
        pipelines_db = await reconcile_experiment_pipelines(
            experiment_id=experiment_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo,
        )
        
        if (pipeline:=next((c for c in pipelines_db if c.id == pipeline_id), None)) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        
        if pipeline.status in {ExperimentPipelineStatusEnum.CREATING, ExperimentPipelineStatusEnum.UPDATING}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pipeline is currently creating or updating. Please try again shortly."
            )
        
        af_dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=pipeline_id,
        )

        if data.name is not None:
            pipeline.name = data.name
        if data.description is not None:
            pipeline.description = data.description

        prefix = experiment_resource_prefix(experiment_id)
        pipeline_ids = [prefix + d.id for d in pipelines_db]
        schedule = data.schedule
        if schedule and schedule.type != "assets":
            schedule = self._check_schedule(schedule)
        else:
            assets = await self.airflow_pipelines.get_assets(pipeline_ids)
            schedule = self._check_schedule(schedule, assets)
        
        params = self._check_params(data.params)

        code = None
        try:
            code = base64.b64decode(data.code_base64).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid base64 code. Please provide a valid base64-encoded UTF-8 string.",
            )
        try:
            validate_pipeline_code(code, prefix)
            
            rm_names = extract_registered_model_names_pipeline_code(code)
            for name in rm_names:
                await self._check_model_ownership(name, experiment.mlflow_experiment_id)
        except PipelineValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            )

        writer = AirflowDagFileWriter()
        writer.write_pipeline(
            pipeline_id=af_dag_id,
            context={
                "mlflow_experiment_id": experiment.mlflow_experiment_id,
                "dag_id": af_dag_id,
                "name": pipeline.name,
                "description": pipeline.description,
                "schedule": schedule,
                "start_date": data.start_date,
                "end_date": data.end_date,
                "catchup": data.catchup,
                "default_args": data.default_args,
                "max_active_runs": data.max_active_runs,
                "dagrun_timeout_seconds": data.dagrun_timeout_seconds,
                "tags": data.tags,
                "params": params,
                "code": code,
            },
        )

        pipeline.status = ExperimentPipelineStatusEnum.UPDATING
        pipeline_up = await self.pipeline_repo.update(pipeline)

        return PipelineReadBase(
            id=pipeline_up.id,
            name=pipeline_up.name,
            description=pipeline_up.description,
            status=pipeline_up.status,
            created_at=pipeline_up.created_at,
            updated_at=pipeline_up.updated_at,
            paused_at=pipeline_up.paused_at,
        )

    async def delete(
        self,
        *,
        experiment_id: str,
        pipeline_id: str,
        current_user: User,
    ):
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment pipelines"
            )
        
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        # Reconcile pipeline
        pipeline = await reconcile_experiment_pipeline(
            experiment_id=experiment_id,
            id=pipeline_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )

        af_dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=pipeline_id,
        )

        writer = AirflowDagFileWriter()
        writer.delete_pipeline(pipeline_id=af_dag_id)
        await self.airflow_pipelines.delete(af_dag_id)

        await self.pipeline_repo.delete(experiment_id, pipeline_id)

    async def activate(
        self,
        *,
        experiment_id: str,
        pipeline_id: str,
        current_user: User,
    ) -> PipelineDetailRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment pipelines"
            )
        
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        # Reconcile pipeline
        pipeline = await reconcile_experiment_pipeline(
            experiment_id=experiment_id,
            id=pipeline_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        
        if pipeline.status != ExperimentPipelineStatusEnum.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pipeline is not paused",
            )

        af_dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=pipeline_id,
        )

        await self.airflow_pipelines.unpause(af_dag_id)
        
        pipeline.status = ExperimentPipelineStatusEnum.ACTIVE
        pipeline.paused_at = None
        await self.pipeline_repo.update(pipeline)

        af = await self.airflow_pipelines.get(af_dag_id)
        assets = await self.airflow_pipelines.get_assets([af_dag_id])
        return self._to_detail(pipeline, af, assets)
    
    async def pause(
        self,
        *,
        experiment_id: str,
        pipeline_id: str,
        current_user: User,
    ) -> PipelineDetailRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment pipelines"
            )
        
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        # Reconcile pipeline
        pipeline = await reconcile_experiment_pipeline(
            experiment_id=experiment_id,
            id=pipeline_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        
        if pipeline.status != ExperimentPipelineStatusEnum.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pipeline is not active",
            )

        af_dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=pipeline_id,
        )

        await self.airflow_pipelines.pause(af_dag_id)
        
        pipeline.status = ExperimentPipelineStatusEnum.PAUSED
        pipeline.paused_at = datetime.utcnow()
        await self.pipeline_repo.update(pipeline)

        af = await self.airflow_pipelines.get(af_dag_id)
        assets = await self.airflow_pipelines.get_assets([af_dag_id])
        return self._to_detail(pipeline, af, assets)
    

    # RUNS

    async def trigger(
        self,
        *,
        experiment_id: str,
        pipeline_id: str,
        conf: Optional[dict],
        current_user: User,
    ) -> RunRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment pipelines"
            )
        
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        # Reconcile pipeline
        pipeline = await reconcile_experiment_pipeline(
            experiment_id=experiment_id,
            id=pipeline_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        if pipeline.status in {ExperimentPipelineStatusEnum.CREATING, ExperimentPipelineStatusEnum.UPDATING}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pipeline is currently creating or updating. Please try again shortly."
            )

        af_dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=pipeline_id,
        )

        af = await self.airflow_pipelines.get(af_dag_id)
        params ={}
        if af and af.get("params"):
            for k, p in af["params"].items():
                params[k] = PipelineParams(
                    value=p.get("value"),
                    type=p.get("schema", {}).get("type", "string"),
                    description=p.get("description"),
                )
        self._validate_conf(conf, params)
        
        run = await self.airflow_runs.trigger(dag_id=af_dag_id, conf=conf)

        return RunRead(
            id=run["dag_run_id"],
            run_type=run.get("run_type"),
            state=run.get("state"),
            triggered_by=run.get("triggered_by"),
            execution_date=run.get("logical_date"),
            duration=run.get("duration"),
        )
    
    async def list_runs(
        self,
        *,
        experiment_id: str,
        pipeline_id: str,
        current_user: User,
        max_runs_analysed: int,
        run_type: ExperimentPipelineRunTypeEnum | None = None,
        state: ExperimentPipelineRunStateEnum | None = None,
        triggered_by: ExperimentPipelineRunTriggeredByEnum | None = None,
        sort: str = "execution_date asc",
    ) -> List[RunRead]:
        _, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment pipeline runs"
            )
        
        if max_runs_analysed <= 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid max_runs_analysed, should be greater than 0"
            )
        
        try:
            sort_field, sort_order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'",
            )

        if sort_field not in ALLOWED_RUN_SORT_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field '{sort_field}'",
            )

        if sort_order not in {"asc", "desc"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sort order must be 'asc' or 'desc'",
            )

        # Reconcile pipeline
        pipeline = await reconcile_experiment_pipeline(
            experiment_id=experiment_id,
            id=pipeline_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )

        af_dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=pipeline_id,
        )

        runs_raw = await self.airflow_runs.list(dag_id=af_dag_id, limit=max_runs_analysed)
        
        runs = [
            RunRead(
                id=r["dag_run_id"],
                run_type=r.get("run_type"),
                state=r.get("state"),
                triggered_by=r.get("triggered_by"),
                execution_date=r.get("logical_date") or r.get("start_date") or r.get("queued_at"),
                duration=self._calculate_duration(r.get("start_date"), r.get("end_date")),
            )
            for r in runs_raw
        ]

        filtered = []
        for r in runs:
            if run_type and r.run_type != run_type:
                continue

            if state and r.state != state:
                continue

            if triggered_by and r.triggered_by != triggered_by:
                continue

            filtered.append(r)

        def sort_key(obj):
            value = getattr(obj, sort_field, None)
            return (value is None, value)

        filtered.sort(
            key=sort_key,
            reverse=(sort_order == "desc"),
        )

        return filtered

    async def get_run(
        self,
        *,
        experiment_id: str,
        pipeline_id: str,
        run_id: str,
        current_user: User,
    ) -> RunDetailRead:
        _, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment pipeline runs"
            )
        
        # Reconcile pipeline
        pipeline = await reconcile_experiment_pipeline(
            experiment_id=experiment_id,
            id=pipeline_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )

        af_dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=pipeline_id,
        )

        run = await self.airflow_runs.get(dag_id=af_dag_id, run_id=run_id)
        if not run or "detail" in run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline run not found"
            )
        
        raw_tasks = await self.airflow_runs.list_task_instances(dag_id=af_dag_id, run_id=run_id)
        tasks_list = []
        for t in raw_tasks:
            state = t.get("state")
            task_id = t.get("task_id")
            try_number = t.get("try_number")
            
            error_data = None
            if state == "failed" and try_number:
                log_json = await self.airflow_runs.get_task_instance_log(
                    dag_id=af_dag_id, run_id=run_id, task_id=task_id, try_number=try_number
                )
                error_data = self._parse_error_from_log(log_json)

            tasks_list.append(
                TaskInstanceRead(
                    task_name=t.get("task_display_name") or task_id,
                    state=state,
                    duration=t.get("duration"),
                    try_number=try_number,
                    error=error_data
                )
            )
        
        version = None
        if run and run.get("dag_versions"):
            version = run["dag_versions"][-1].get("version_number")

        start = run.get("start_date")
        end = run.get("end_date")

        return RunDetailRead(
            id=run["dag_run_id"],
            run_type=run.get("run_type"),
            state=run.get("state"),
            triggered_by=run.get("triggered_by"),
            execution_date=run.get("logical_date") or start or run.get("queued_at"),
            duration=self._calculate_duration(start, end),
            started_at=start,
            finished_at=end,
            dag_version=version,
            conf=run.get("conf"),
            tasks=tasks_list,
        )

    async def delete_run(
        self,
        *,
        experiment_id: str,
        pipeline_id: str,
        run_id: str,
        current_user: User,
    ):
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment pipeline runs"
            )
        
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        # Reconcile pipeline
        pipeline = await reconcile_experiment_pipeline(
            experiment_id=experiment_id,
            id=pipeline_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )

        af_dag_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=pipeline_id,
        )

        run = await self.airflow_runs.get(dag_id=af_dag_id, run_id=run_id)
        if not run or "detail" in run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline run not found"
            )
        
        await self.airflow_runs.delete(dag_id=af_dag_id, run_id=run_id)

    
    # Helpers
    
    def _to_read(
        self,
        db: ExperimentPipeline,
        af: Optional[dict],
    ) -> PipelineRead:      
        tags = None
        if af:
            tags = [t.get("name") for t in af.get("tags", [])]

        return PipelineRead(
            id=db.id,
            name=db.name,
            description=db.description,
            status=db.status,
            tags=tags,
            schedule=af.get("timetable_summary") if af else None,
            schedule_description=af.get("timetable_description") if af else None,
            next_run=af.get("next_dagrun_run_after") if af else None,
            created_at=db.created_at,
            updated_at=db.updated_at,
            paused_at=db.paused_at,
        )

    def _to_read_error(
        self,
        db: ExperimentPipeline,
        errors: list,
    ) -> PipelineReadError:
        return PipelineReadError(
            id=db.id,
            name=db.name,
            description=db.description,
            status=ExperimentPipelineStatusEnum.ERROR,
            warnings=[e.get("stack_trace") for e in errors],
            created_at=db.created_at,
            updated_at=db.updated_at,
            paused_at=db.paused_at,
        )

    def _to_detail(
        self,
        db: ExperimentPipeline,
        af: dict,
        assets: dict,
    ) -> PipelineDetailRead:
        base = self._to_read(db, af)
        dag_id = af.get("dag_id")

        params ={}
        if af and af.get("params"):
            for k, p in af["params"].items():
                params[k] = PipelineParams(
                    value=p.get("value"),
                    type=p.get("schema", {}).get("type", "string"),
                    description=p.get("description"),
                )

        version = None
        if af and af.get("latest_dag_version"):
            version = af["latest_dag_version"].get("version_number")

        consuming = []
        producing = []
        for asset in assets:
            if any(d["dag_id"] == dag_id for d in asset.get("consuming_dags", [])):
                consuming.append(asset["name"])
            if any(t["dag_id"] == dag_id for t in asset.get("producing_tasks", [])):
                producing.append(asset["name"])

        writer = AirflowDagFileWriter()
        dag_hash = writer.calculate_dag_hash(pipeline_id=dag_id)
        if dag_hash is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )

        return PipelineDetailRead(
            **base.dict(),
            catchup=af.get("catchup"),
            start_date=af.get("start_date"),
            end_date=af.get("end_date"),
            timezone=af.get("timezone"),
            params=params,
            max_active_runs=af.get("max_active_runs"),
            version=version,
            assets=PipelineAssets(consuming=consuming, producing=producing),
            dag_hash=writer.calculate_dag_hash(pipeline_id=dag_id),
            created_by=PipelineCreator(
                user_id=db.created_by.id,
                email=db.created_by.email,
            ),
        )

    def _to_detail_error(
        self,
        db: ExperimentPipeline,
        errors: list,
    ) -> PipelineDetailReadError:
        base = self._to_read_error(db, errors)

        return PipelineDetailReadError(
            **base.dict(),
            created_by=PipelineCreator(
                user_id=db.created_by.id,
                email=db.created_by.email,
            ),
        )
    
    def _check_schedule(
            self,
            schedule: PipelineSchedule,
            assets: list = None,
    ) -> PipelineSchedule | None:
        if not schedule:
            return None
        
        type = schedule.type
        value = schedule.value
        presets = {'@once', '@hourly', '@daily', '@weekly', '@monthly', '@quarterly', '@yearly', '@continuous'}
        try:
            details = ""
            if type == "cron":
                if not isinstance(value, str) or not croniter.is_valid(value):
                    details = "Invalid cron expression."
                    raise ValueError()
                
            elif type == "preset":
                if value not in presets:
                    details = f"Valid options '{presets}'."
                    raise ValueError()
                
            elif type == "interval_seconds":
                if not isinstance(value, int) or value <= 0:
                    details = "The value must be an integer greater than 0."
                    raise ValueError()
                
            elif type == "assets":
                if not (isinstance(value, list) and all(isinstance(i, str) for i in value)):
                    details = "Provide a list of asset names."
                    raise ValueError()
                
                normalized_assets = []
                for asset_name in value:
                    asset = next((a for a in assets if a.get("name") == asset_name), None)
                    if asset is None:
                        details=f"Invalid asset '{asset_name}'."
                        raise ValueError()

                    normalized_assets.append({
                        "name": asset.get("name"),
                        "uri": asset.get("uri"),
                    })

                schedule.value = normalized_assets
                
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid schedule type '{type}'",
                )
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid value for schedule type '{type}'. " + details,
            )

        return schedule
    
    def _check_params(
            self,
            params: dict,
    ) -> dict:
        if not params:
            return params

        normalized = {}

        for name, p in params.items():
            p_type = p.type
            value = p.value
            description = p.description

            try:
                if p_type == "string":
                    value = str(value)
                elif p_type == "integer":
                    if isinstance(value, bool):
                        raise ValueError()
                    value = int(value)
                elif p_type == "number":
                    value = float(value)
                elif p_type == "boolean":
                    value = bool(value)
                elif p_type == "array":
                    if not isinstance(value, list):
                        raise ValueError()
                elif p_type == "object":
                    if not isinstance(value, dict):
                        raise ValueError()
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid param type '{p_type}' for param '{name}'",
                    )
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid value for param '{name}' with type '{p_type}'",
                )

            normalized[name] = {
                "type": p_type,
                "value": value,
                "description": description,
            }

        return normalized
    
    def _calculate_duration(self, start, end):
        if not start or not end:
            return None

        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

        return (end_dt - start_dt).total_seconds()
    
    def _validate_conf(self, conf: dict, pipeline_params: dict):
        if not conf:
            return
        
        TYPE_MAP = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        for key, value in conf.items():
            if key not in pipeline_params:
                continue

            expected_type = pipeline_params[key].type
            py_type = TYPE_MAP.get(expected_type)

            if py_type and not isinstance(value, py_type):
                raise HTTPException(
                    status_code=400,
                    detail=f"Parameter '{key}' must be of type '{expected_type}'"
                )
            
    def _parse_error_from_log(self, log_data: Dict) -> Optional[TaskErrorRead]:
        content = log_data.get("content", [])

        for entry in reversed(content):
            if entry.get("level") == "error" and "error_detail" in entry:
                details = entry["error_detail"]
                if details and isinstance(details, list):
                    err = details[0]
                    return TaskErrorRead(
                        type=err.get("exc_type", "Exception"),
                        value=err.get("exc_value", "Unknown error")
                    )
        return None
    
    async def _check_model_ownership(
        self,
        name: str,
        mlflow_id: str,
    ):
        existing_versions = await self.mlflow_registered_models.list_registered_model_versions(name)
        if existing_versions:
            v1_run = self.mlflow_registered_models.client.get_run(existing_versions[-1].run_id)
            if str(v1_run.info.experiment_id) != mlflow_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail=f"Registered name '{name}' is owned by another experiment"
                )
