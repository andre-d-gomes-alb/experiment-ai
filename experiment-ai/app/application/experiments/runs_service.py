from fastapi import HTTPException, status
from typing import List, Optional, Dict
from datetime import datetime
import json

from app.infrastructure.db.models import User
from app.infrastructure.db.repositories import ExperimentRepository
from app.infrastructure.mlflow import MlflowExperimentRunService
from app.domain.experiments import can_view_experiment, can_edit_experiment
from app.api.v1.experiments.runs import (
    RunRead, RunDetailRead,
    RunLoggedModelInfo, RunModelPromptInfo, RunArtifactRead, RunDatasetInputInfo, RunInputModelInfo,
)
from app.core.resource_keys import experiment_resource_prefix


ALLOWED_SORT_FIELDS = {
    "id",
    "run_name",
    "status",
    "lifecycle_stage",
    "start_time",
    "duration"
}


class ExperimentRunsService:
    def __init__(
        self,
        experiment_repo: ExperimentRepository,
        mlflow_runs: MlflowExperimentRunService,
    ):
        self.experiment_repo = experiment_repo
        self.mlflow_runs = mlflow_runs

    async def list(
        self,
        *,
        experiment_id: str,
        current_user: User,
        run_name: str | None = None,
        r_status: str | None = None,
        metrics: str | None = None,
        has_models: bool | None = None,
        include_deleted: bool = False,
        sort: str = "start_time desc",
    ) -> List[RunRead]:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment runs"
            )
        
        try:
            sort_field, sort_order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'",
            )

        if sort_field not in ALLOWED_SORT_FIELDS and not sort_field.startswith("metric_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field '{sort_field}'",
            )

        if sort_order not in {"asc", "desc"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sort order must be 'asc' or 'desc'",
            )

        mlflow_id = str(experiment.mlflow_experiment_id)
        view_type = 3 if include_deleted else 1
        raw_runs = await self.mlflow_runs.list(mlflow_id, view_type=view_type)

        runs = []
        for run in raw_runs:
            logged_models = self._extract_logged_models(run)
            if has_models is not None:
                if has_models and not logged_models:
                    continue
                if not has_models and logged_models:
                    continue

            runs.append(
                RunRead(
                    id=run.info.run_id,
                    run_name=run.info.run_name,
                    status=run.info.status,
                    lifecycle_stage=run.info.lifecycle_stage,
                    start_time=self._ms_to_datetime(run.info.start_time),
                    duration=self._get_duration(run.info.start_time, run.info.end_time),
                    metrics=run.data.metrics,
                    logged_models=logged_models,
                )
            )

        filtered = []
        target_metrics = [m.strip() for m in metrics.split(",")] if metrics else []

        for r in runs:
            if run_name and run_name.lower() not in r.run_name.lower():
                continue
            
            if r_status and r.status != r_status.upper():
                continue
            
            if target_metrics:
                if not all(m in r.metrics for m in target_metrics):
                    continue

            filtered.append(r)

        if filtered and sort_field.startswith("metric_"):
            m_name = sort_field.replace("metric_", "")
            if not any(m_name in r.metrics for r in filtered):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Metric '{m_name}' not found to perform sorting."
                )

        def get_sort_value(run_obj: RunRead):
            if sort_field.startswith("metric_"):
                m_name = sort_field.replace("metric_", "")
                val = run_obj.metrics.get(m_name)
            elif sort_field == "status":
                val = sort_field.upper() if sort_field else None
            else:
                val = getattr(run_obj, sort_field, None)
            return (val is None, val)

        filtered.sort(
            key=get_sort_value,
            reverse=(sort_order == "desc")
        )

        return filtered

    async def get(
        self,
        *,
        experiment_id: str,
        run_id: str,
        current_user: User,
    ) -> RunDetailRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment runs"
            )
        
        run = await self.mlflow_runs.get(run_id)        
        if not run or str(run.info.experiment_id) != str(experiment.mlflow_experiment_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found"
            )

        artifacts_raw = await self.mlflow_runs.list_artifacts(run_id)

        dataset_inputs = []
        model_inputs = []
        if hasattr(run, 'inputs'):
            if run.inputs.dataset_inputs:
                dataset_inputs = [
                    RunDatasetInputInfo(
                        name=d.dataset.name,
                        source_type=d.dataset.source_type,
                        digest=d.dataset.digest
                    ) for d in run.inputs.dataset_inputs
                ]
            if run.inputs.model_inputs:
                model_inputs = [
                    RunInputModelInfo(model_id=m.model_id)
                    for m in run.inputs.model_inputs
                ]
        
        return RunDetailRead(
            id=run.info.run_id,
            run_name=run.info.run_name,
            status=run.info.status,
            lifecycle_stage=run.info.lifecycle_stage,
            start_time=self._ms_to_datetime(run.info.start_time),
            duration=self._get_duration(run.info.start_time, run.info.end_time),
            metrics=run.data.metrics,
            params=run.data.params,
            tags={k: v for k, v in run.data.tags.items() if not k.startswith("mlflow.")},
            dataset_inputs=dataset_inputs,
            model_inputs=model_inputs,
            logged_models=self._extract_logged_models(run),
            linked_prompts=self._extract_linked_prompts(run.data.tags),
            artifacts=[
                RunArtifactRead(
                    path=art.path,
                    is_dir=art.is_dir
                )
                for art in artifacts_raw
            ],
        )

    async def delete(
        self,
        *,
        experiment_id: str,
        run_id: str,
        current_user: User,
    ) -> None:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment runs"
            )
            
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        run = await self.mlflow_runs.get(run_id)
        if not run or str(run.info.experiment_id) != str(experiment.mlflow_experiment_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found"
            )
        if run.info.lifecycle_stage == "deleted":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run already deleted"
            )

        await self.mlflow_runs.delete(run_id)

    async def download_artifacts_zip(
        self, 
        *,
        experiment_id: str, 
        run_id: str,
        current_user: User,
    ):
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment runs"
            )

        run = await self.mlflow_runs.get(run_id)
        if not run or str(run.info.experiment_id) != str(experiment.mlflow_experiment_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found"
            )
        
        zip_buffer = await self.mlflow_runs.get_artifacts_as_zip(run_id)
        if not zip_buffer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No artifacts found for this run"
            )
        
        prefix = experiment_resource_prefix(experiment_id)
        return zip_buffer, f"{prefix}run_{run_id}__artifacts.zip"
    

    # Helpers

    def _ms_to_datetime(self, ms: int) -> Optional[datetime]:
        if ms is None:
            return None
        return datetime.fromtimestamp(ms / 1000.0)
    
    def _get_duration(self, start: Optional[int], end: Optional[int]) -> Optional[int]:
        if start and end:
            return end - start
        return None
    
    def _extract_logged_models(self, run) -> List[RunLoggedModelInfo]:
        if hasattr(run, 'outputs') and run.outputs.model_outputs:
            return [
                RunLoggedModelInfo(
                    model_id=m.model_id,
                    step=m.step
                )
                for m in run.outputs.model_outputs
            ]
        
        # Fallback to legacy tag-based logged model info
        tags = getattr(run.data, 'tags', {})
        history_json = tags.get("mlflow.log-model.history")
        if history_json:
            try:
                import json
                history = json.loads(history_json)
                if isinstance(history, list):
                    return [
                        RunLoggedModelInfo(model_id=item.get("model_uuid"), step=0) 
                        for item in history if item.get("model_uuid")
                    ]
            except Exception:
                pass

        return []
        
    def _extract_linked_prompts(self, tags: Dict[str, str]) -> List[RunModelPromptInfo]:
        prompts_json = tags.get("mlflow.linkedPrompts")
        if not prompts_json:
            return []
        
        try:
            prompts_data = json.loads(prompts_json)
            if not isinstance(prompts_data, list):
                return []
            
            return [
                RunModelPromptInfo(
                    name=p.get("name"),
                    version=str(p.get("version"))
                ) for p in prompts_data if p.get("name")
            ]
        except Exception:
            return []
