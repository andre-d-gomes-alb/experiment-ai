from fastapi import HTTPException, status
from typing import List
from datetime import datetime
import json

from app.infrastructure.db.models import User
from app.infrastructure.db.repositories import ExperimentRepository
from app.infrastructure.mlflow import MlflowExperimentLoggedModelService, MlflowExperimentRegisteredModelService
from app.domain.experiments import can_view_experiment, can_edit_experiment, ExperimentLoggedModelStatusEnum
from app.api.v1.experiments.logged_models import (
    LoggedModelRead, LoggedModelDetailRead, LoggedModelUpdate, LoggedModelRegisteredInfo,
    LoggedModelRegister, LoggedModelRegisterRead,
)
from app.core.resource_keys import experiment_resource_prefix


ALLOWED_SORT_FIELDS = {
    "id",
    "name",
    "run_id",
    "created_at",
    "updated_at",
    "registered_count"
}


class ExperimentLoggedModelsService:
    def __init__(
        self,
        experiment_repo: ExperimentRepository,
        mlflow_models: MlflowExperimentLoggedModelService,
        mlflow_registered_models: MlflowExperimentRegisteredModelService,
    ):
        self.experiment_repo = experiment_repo
        self.mlflow_models = mlflow_models
        self.mlflow_registered_models = mlflow_registered_models

    async def list_logged_models(
        self,
        *,
        experiment_id: str,
        current_user: User,
        name: str | None = None,
        run_id: str | None = None,
        tags: str | None = None,
        params: str | None = None,
        metrics: str | None = None,
        has_registered: bool | None = None,
        m_status: ExperimentLoggedModelStatusEnum | str = ExperimentLoggedModelStatusEnum.READY,
        sort: str = "created_at desc",
    ) -> List[LoggedModelRead]:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment logged models"
            )
        
        try:
            sort_field, sort_order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'",
            )

        if sort_field not in ALLOWED_SORT_FIELDS and \
            not any(sort_field.startswith(sf) for sf in ["param_", "metric_"]):
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
        status_int = self.STATUS_MAP.get(m_status.value.lower(), 2)
        raw_models = await self.mlflow_models.list_logged_models(mlflow_id, status_int)
        models = [self._map_to_read_schema(m) for m in raw_models]
        
        filtered = []

        def parse_kv_filter(filter_str: str):
            pairs = [p.strip() for p in filter_str.split(",")]
            result = {}
            for p in pairs:
                if ":" in p:
                    k, v = p.split(":", 1)
                    result[k.strip()] = v.strip()
                else:
                    result[p.strip()] = None
            return result
        
        target_tags = parse_kv_filter(tags) if tags else {}
        target_params = parse_kv_filter(params) if params else {}
        target_metrics = [m.strip() for m in metrics.split(",")] if metrics else []

        for m in models:
            if name and name.lower() not in m.name.lower():
                continue
            
            if run_id and run_id not in m.run_id:
                continue
            
            if has_registered is not None:
                if has_registered and m.registered_count == 0:
                    continue
                if not has_registered and m.registered_count > 0:
                    continue

            if target_tags:
                match = True
                for k, v in target_tags.items():
                    if k not in m.tags or (v is not None and m.tags[k] != v):
                        match = False
                        break
                if not match:
                    continue

            if target_params:
                match = True
                for k, v in target_params.items():
                    if k not in m.params or (v is not None and m.params[k] != v):
                        match = False
                        break
                if not match:
                    continue
            if target_metrics:
                if not all(metric_key in m.metrics for metric_key in target_metrics):
                    continue
            filtered.append(m)

        if filtered:
            if sort_field.startswith("metric_"):
                m_key = sort_field.replace("metric_", "")
                if not any(m_key in obj.metrics for obj in filtered):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, 
                        detail=f"Metric '{m_key}' not found to perform sorting."
                    )
            elif sort_field.startswith("param_"):
                p_key = sort_field.replace("param_", "")
                if not any(p_key in obj.params for obj in filtered):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, 
                        detail=f"Parameter '{p_key}' not found to perform sorting."
                    )

        def get_sort_value(obj: LoggedModelRead):
            if sort_field.startswith("metric_"):
                val = obj.metrics.get(sort_field.replace("metric_", ""))
            elif sort_field.startswith("param_"):
                val = obj.params.get(sort_field.replace("param_", ""))
            else:
                val = getattr(obj, sort_field, None)
            return (val is None, val)

        filtered.sort(key=get_sort_value, reverse=(sort_order == "desc"))

        return filtered

    async def get_logged_model(
        self,
        *,
        experiment_id: str,
        model_id: str,
        current_user: User,
    ) -> LoggedModelDetailRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment logged models"
            )

        m = await self.mlflow_models.get_logged_model(model_id)
        if not m or str(m.experiment_id) != str(experiment.mlflow_experiment_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Logged model not found"
            )

        base_data = self._map_to_read_schema(m)
        reg_models = self._parse_registered_models(m)
        
        return LoggedModelDetailRead(
            **base_data.dict(),
            registered_models=reg_models,
            model_type=m.model_type
        )

    async def update_logged_model(
        self,
        *,
        experiment_id: str,
        model_id: str,
        obj_in: LoggedModelUpdate,
        current_user: User,
    ) -> LoggedModelRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment logged models"
            )
            
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        m = await self.mlflow_models.get_logged_model(model_id)
        if not m or str(m.experiment_id) != str(experiment.mlflow_experiment_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Logged model not found"
            )

        await self.mlflow_models.update_logged_model_metadata(
            model_id=model_id,
            status=obj_in.status.value.upper() if obj_in.status else None,
            tags=obj_in.tags
        )

        upd_model = await self.mlflow_models.get_logged_model(model_id)
        
        return self._map_to_read_schema(upd_model)

    async def delete_logged_model(
        self,
        *,
        experiment_id: str,
        model_id: str,
        current_user: User,
    ):
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment logged models"
            )
            
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        m = await self.mlflow_models.get_logged_model(model_id)
        if not m or str(m.experiment_id) != str(experiment.mlflow_experiment_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Logged model not found"
            )

        await self.mlflow_models.delete_logged_model(model_id)
    
    async def download_model_zip(
        self, 
        *,
        experiment_id: str, 
        model_id: str, 
        current_user: User,
    ):
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment logged models"
            )

        m = await self.mlflow_models.get_logged_model(model_id)
        if not m or str(m.experiment_id) != str(experiment.mlflow_experiment_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Logged model not found"
            )
        
        zip_buffer = await self.mlflow_models.download_logged_model_as_zip(m.model_uri)
        if not zip_buffer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="No artifacts found for this model"
            )
        
        prefix = experiment_resource_prefix(experiment_id)
        filename = f"{prefix}model_{model_id}.zip"
        
        return zip_buffer, filename
    
    async def register_logged_model(
        self,
        experiment_id: str,
        model_id: str,
        obj_in: LoggedModelRegister,
        current_user: User,
    ) -> LoggedModelRegisterRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment logged models"
            )
            
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        mlflow_id = str(experiment.mlflow_experiment_id)
        m = await self.mlflow_models.get_logged_model(model_id)
        if not m or str(m.experiment_id) != mlflow_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Logged model not found"
            )

        existing_versions = await self.mlflow_registered_models.list_registered_model_versions(obj_in.name)
        if existing_versions:
            v1_run = self.mlflow_registered_models.client.get_run(existing_versions[-1].run_id)
            if str(v1_run.info.experiment_id) != mlflow_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail=f"Registered name '{obj_in.name}' is owned by another experiment"
                )
            
        new_version = await self.mlflow_models.register_model(
            model_uri=m.model_uri,
            name=obj_in.name,
            run_id=m.source_run_id,
            model_id=model_id,
            description=obj_in.description,
            tags=obj_in.tags,
            aliases=obj_in.aliases
        )

        m_parent = await self.mlflow_registered_models.get_registered_model(obj_in.name)
        metrics = {met.key: met.value for met in m.metrics} if m.metrics else {}
        params = m.params or {}
        model_aliases_dict = m_parent.aliases if m_parent.aliases else {}
        version_aliases = [
            alias for alias, ver in model_aliases_dict.items() 
            if str(ver) == str(new_version.version)
        ]

        return LoggedModelRegisterRead(
            registered_name=new_version.name,
            version=new_version.version,
            description=new_version.description,
            status=new_version.status,
            run_id=m.source_run_id,
            model_id=model_id,
            tags=new_version.tags or {},
            params=params,
            metrics=metrics,
            aliases=version_aliases,
            created_at=datetime.fromtimestamp(new_version.creation_timestamp / 1000.0),
            updated_at=datetime.fromtimestamp(new_version.last_updated_timestamp / 1000.0)
        )


    # Helpers

    STATUS_MAP = {
        "unspecified": 0,
        "pending": 1,
        "ready": 2,
        "failed": 3
    }

    def _map_to_read_schema(self, m) -> LoggedModelRead:
        registered_models = self._parse_registered_models(m)
        metrics = {met.key: met.value for met in m.metrics} if m.metrics else {}
        tags = {k: v for k, v in (m.tags or {}).items() if not k.startswith("mlflow.")}
        
        return LoggedModelRead(
            id=m.model_id,
            name=m.name,
            run_id=m.source_run_id,
            status=m.status.value.lower() if m.status is not None else ExperimentLoggedModelStatusEnum.UNSPECIFIED,
            tags=tags,
            params=m.params or {},
            metrics=metrics,
            created_at=datetime.fromtimestamp(m.creation_timestamp / 1000.0),
            updated_at=datetime.fromtimestamp(m.last_updated_timestamp / 1000.0),
            registered_count=len(registered_models)
        )

    def _map_to_detail_schema(self, m) -> LoggedModelDetailRead:
        base_data = self._map_to_read_schema(m)
        registered_models = self._parse_registered_models(m)
        
        return LoggedModelDetailRead(
            **base_data.dict(),
            registered_models=registered_models,
            model_type=m.model_type
        )

    def _parse_registered_models(self, m) -> List[LoggedModelRegisteredInfo]:
        if not m.tags:
            return []
        
        versions_raw = m.tags.get("mlflow.modelVersions", "[]")
        try:
            data = json.loads(versions_raw)

            unique_versions = set()
            result = []
            for v in data:
                name = v.get("name")
                version = str(v.get("version"))
                identifier = (name, version)
                if name and version and identifier not in unique_versions:
                    unique_versions.add(identifier)
                    result.append(
                        LoggedModelRegisteredInfo(name=name, version=version)
                    )
            return result
        except:
            return []
