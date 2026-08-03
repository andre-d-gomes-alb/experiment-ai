from fastapi import HTTPException, status
from typing import List, Dict
from datetime import datetime
import re
import json

from app.infrastructure.db.models import User
from app.infrastructure.db.repositories import ExperimentRepository, ExperimentRegisteredModelRepository
from app.infrastructure.mlflow import (
    MlflowExperimentRegisteredModelService, MlflowExperimentRunService, MlflowExperimentService,
)
from app.domain.experiments import can_view_experiment, can_edit_experiment
from app.api.v1.experiments.registered_models import (
    RegisteredModelRead, RegisteredModelDetailRead, RegisteredModelUpdate, RegisteredModelVersionRead,
    RegisteredModelVersionUpdate, RegisteredModelVersionDetailRead, RegisteredModelAliasesRead,
    RegisteredModelVersionPromote, RegisteredModelVersionPromoteRead,
)
from app.core.resource_keys import experiment_resource_prefix


ALLOWED_SORT_FIELDS = {
    "name",
    "is_private",
    "created_at",
    "updated_at",
}

ALLOWED_VERSION_SORT_FIELDS = {
    "version",
    "run_id",
    "model_id",
    "created_at",
    "updated_at"
}


class ExperimentRegisteredModelsService:
    def __init__(
        self,
        experiment_repo: ExperimentRepository,
        experiment_registered_model_repo: ExperimentRegisteredModelRepository,
        mlflow_experiments: MlflowExperimentService,
        mlflow_runs: MlflowExperimentRunService,
        mlflow_models: MlflowExperimentRegisteredModelService
    ):
        self.experiment_repo = experiment_repo
        self.experiment_registered_model_repo = experiment_registered_model_repo
        self.mlflow_ext = mlflow_experiments
        self.mlflow_runs = mlflow_runs
        self.mlflow_models = mlflow_models

    async def list_registered_models(
        self,
        experiment_id: str,
        current_user: User,
        tags: str | None = None,
        aliases: str | None = None,
        is_private: bool | None = None,
        sort: str = "created_at desc",
    ) -> List[RegisteredModelRead]:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment registered models"
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
        
        all_models = await self.mlflow_models.list_registered_models()
        results = []
        for m in all_models:
            if await self._verify_ownership(m.name, str(experiment.mlflow_experiment_id)):
                latest = m.latest_versions[0] if m.latest_versions else None
                results.append(await self._map_model(m, latest))
        
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
        target_aliases = [a.strip() for a in aliases.split(",")] if aliases else []

        filtered = []
        for m in results:
            if target_aliases:
                model_alias_names = {a.alias for a in m.aliases}
                if not all(target in model_alias_names for target in target_aliases):
                    continue

            if target_tags:
                match = True
                for k, v in target_tags.items():
                    if k not in m.tags or (v is not None and m.tags[k] != v):
                        match = False
                        break
                if not match:
                    continue

            if is_private is not None:
                if m.is_private != is_private:
                    continue

            filtered.append(m)

        def get_sort_value(obj: RegisteredModelRead):
            val = getattr(obj, sort_field, None)
            return (val is None, val)

        filtered.sort(key=get_sort_value, reverse=(sort_order == "desc"))

        return filtered

    async def get_registered_model(
        self,
        experiment_id: str,
        name: str,
        current_user: User,
    ) -> RegisteredModelDetailRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment registered models"
            )

        mlflow_id = str(experiment.mlflow_experiment_id)
        if not await self._verify_ownership(name, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model not found"
            )
        
        m = await self.mlflow_models.get_registered_model(name)
        latest_v = m.latest_versions[0] if m.latest_versions else None
        latest_detail = None
        if latest_v:
            base_v = await self._map_version(latest_v, m.aliases if m.aliases else {})
            model_info = await self.mlflow_models.get_registered_model_version_info(name, latest_v.version)
            latest_detail = self._map_version_detail(base_v, model_info)

        privacy = await self.experiment_registered_model_repo.get_privacy(model_name=m.name)

        return RegisteredModelDetailRead(
            name=m.name,
            description=m.description,
            tags=m.tags or {},
            aliases=[
                RegisteredModelAliasesRead(alias=k, version=v)
                for k, v in (m.aliases or {}).items()
            ],
            latest_version=latest_detail,
            is_private=privacy,
            created_at=datetime.fromtimestamp(m.creation_timestamp / 1000.0),
            updated_at=datetime.fromtimestamp(m.last_updated_timestamp / 1000.0),
        )

    async def update_registered_model(
        self,
        experiment_id: str,
        name: str,
        obj_in: RegisteredModelUpdate,
        current_user: User,
    ) -> RegisteredModelRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment registered models"
            )
            
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        if not await self._verify_ownership(name, str(experiment.mlflow_experiment_id)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model not found"
            )
        
        if obj_in.name and obj_in.name != name:
            check_name = await self.mlflow_models.get_registered_model(obj_in.name)
            if check_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Registered model '{obj_in.name}' already exists."
                )
        
        up_m = await self.mlflow_models.update_registered_model(
            name=name,
            new_name=obj_in.name,
            description=obj_in.description,
            tags=obj_in.tags
        )

        latest = up_m.latest_versions[0] if up_m.latest_versions else None

        if obj_in.is_private is not None:
            await self.experiment_registered_model_repo.set_privacy(
                model_name=name,
                experiment_id=experiment.id,
                user_id=current_user.id,
                is_private=obj_in.is_private,
            )

        return await self._map_model(up_m, latest)

    async def delete_registered_model(
        self,
        experiment_id: str,
        name: str,
        current_user: User,
    ):
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment registered models"
            )
            
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        if not await self._verify_ownership(name, str(experiment.mlflow_experiment_id)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model not found"
            )
        
        await self.mlflow_models.delete_registered_model(name)


    # VERSIONS

    async def list_registered_model_versions(
        self,
        experiment_id: str,
        name: str,
        current_user: User,
        run_id: str | None = None,
        model_id: str | None = None,
        tags: str | None = None,
        params: str | None = None,
        metrics: str | None = None,
        aliases: str | None = None,
        is_ready: bool | None = None,
        sort: str = "version desc",
    ) -> List[RegisteredModelVersionRead]:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment registered models"
            )

        mlflow_id = str(experiment.mlflow_experiment_id)
        if not await self._verify_ownership(name, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model not found"
            )
        
        try:
            sort_field, sort_order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'",
            )

        if sort_field not in ALLOWED_VERSION_SORT_FIELDS and \
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
        
        raw_versions = await self.mlflow_models.list_registered_model_versions(name)
        model_obj = await self.mlflow_models.get_registered_model(name)
        
        versions = []
        for v in raw_versions:
            if await self._is_version_from_exp(v, mlflow_id):
                versions.append(await self._map_version(v, model_obj.aliases if model_obj.aliases else []))

        def parse_kv(s):
            if not s: return {}
            res = {}
            for p in s.split(","):
                if ":" in p:
                    k, v = p.split(":", 1)
                    res[k.strip()] = v.strip()
                else:
                    res[p.strip()] = None
            return res

        target_tags = parse_kv(tags)
        target_params = parse_kv(params)
        target_metrics = [m.strip() for m in metrics.split(",")] if metrics else []
        target_aliases = [a.strip() for a in aliases.split(",")] if aliases else []

        filtered = []
        for v in versions:
            if is_ready is not None:
                v_is_ready = v.status.upper() == "READY"
                if v_is_ready != is_ready:
                    continue

            if run_id and (not v.run_id or run_id not in v.run_id):
                continue

            if model_id:
                if not v.model_id or model_id not in v.model_id:
                    continue

            if target_tags:
                if not all(k in v.tags and (v_val is None or v.tags[k] == v_val) for k, v_val in target_tags.items()):
                    continue

            if target_params:
                if not all(k in v.params and (v_val is None or v.params[k] == v_val) for k, v_val in target_params.items()):
                    continue

            if target_metrics:
                if not all(m_key in v.metrics for m_key in target_metrics):
                    continue

            if target_aliases:
                if not any(alias in v.aliases for alias in target_aliases):
                    continue

            filtered.append(v)

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

        def get_sort_value(obj: RegisteredModelVersionRead):
            if sort_field.startswith("metric_"):
                val = obj.metrics.get(sort_field.replace("metric_", ""))
            elif sort_field.startswith("param_"):
                val = obj.params.get(sort_field.replace("param_", ""))
            else:
                val = getattr(obj, sort_field, None)
                if sort_field == "version":
                    try: val = int(val)
                    except: pass
            return (val is None, val)

        filtered.sort(key=get_sort_value, reverse=(sort_order == "desc"))

        return filtered
    
    async def get_registered_model_version(
        self,
        experiment_id: str,
        name: str,
        version: str,
        current_user: User,
    ) -> RegisteredModelVersionDetailRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment registered models"
            )

        mlflow_id = str(experiment.mlflow_experiment_id)
        if not await self._verify_ownership(name, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model not found"
            )
        
        m_version = await self.mlflow_models.get_registered_model_version(name, version)
        if not m_version or not await self._is_version_from_exp(m_version, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model version not found"
            )
        
        base_read = await self._map_version(m_version)
        model_info = await self.mlflow_models.get_registered_model_version_info(name, m_version.version)
        
        return self._map_version_detail(base_read, model_info)

    async def update_registered_model_version(
        self,
        experiment_id: str,
        name: str,
        version: str,
        obj_in: RegisteredModelVersionUpdate,
        current_user: User,
    ) -> RegisteredModelVersionRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment registered models"
            )
            
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        mlflow_id = str(experiment.mlflow_experiment_id)
        if not await self._verify_ownership(name, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model not found"
            )
        
        m_version = await self.mlflow_models.get_registered_model_version(name, version)
        if not m_version or not await self._is_version_from_exp(m_version, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model version not found"
            )
        
        updated = await self.mlflow_models.update_registered_model_version(
            name=name,
            version=m_version.version,
            description=obj_in.description,
            tags=obj_in.tags,
            aliases=obj_in.aliases
        )

        return await self._map_version(updated)

    async def delete_registered_model_version(
        self,
        experiment_id: str,
        name: str,
        version: str,
        current_user: User,
    ):
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment registered models"
            )
            
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        mlflow_id = str(experiment.mlflow_experiment_id)
        if not await self._verify_ownership(name, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model not found"
            )
        
        raw_versions = await self.mlflow_models.list_registered_model_versions(name)
        model_obj = await self.mlflow_models.get_registered_model(name)
        versions = []
        for v in raw_versions:
            if await self._is_version_from_exp(v, mlflow_id):
                versions.append(await self._map_version(v, model_obj.aliases if model_obj.aliases else []))
        target_version = next((v for v in versions
                               if str(v.version) == str(version) or
                               (v.aliases and str(version) in v.aliases)), None)
        if not target_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model version not found"
            )
        if len(raw_versions) == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"This is the last version of model '{name}'. "
                    "If you truly want to delete this, please delete the entire 'Registered Model' entity."
                )
            )
        
        await self.mlflow_models.delete_model_version(name, target_version.version)

    async def download_registered_model_version_zip(
        self,
        experiment_id: str,
        name: str,
        version: str,
        current_user: User,
    ):
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment registered models"
            )

        mlflow_id = str(experiment.mlflow_experiment_id)
        if not await self._verify_ownership(name, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model not found"
            )
        
        m_version = await self.mlflow_models.get_registered_model_version(name, version)
        if not m_version or not await self._is_version_from_exp(m_version, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model version not found"
            )
        
        zip_buffer = await self.mlflow_models.download_model_version_as_zip(m_version.source)
        if not zip_buffer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="No artifacts found for this model"
            )
        
        prefix = experiment_resource_prefix(experiment_id)
        filename = f"{prefix}registered_model_{name}__version_{version}.zip"
        
        return zip_buffer, filename
    
    async def promote_registered_model_version(
        self,
        experiment_id: str,
        name: str,
        version: str,
        target: RegisteredModelVersionPromote,
        current_user: User,
    ) -> RegisteredModelVersionPromoteRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment registered models"
            )
            
        if experiment.archived_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        mlflow_id = str(experiment.mlflow_experiment_id)
        if not await self._verify_ownership(name, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model not found"
            )
        
        m_version = await self.mlflow_models.get_registered_model_version(name, version)
        if not m_version or not await self._is_version_from_exp(m_version, mlflow_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered model version not found"
            )
        
        existing_versions = await self.mlflow_models.list_registered_model_versions(target.target_name)
        if existing_versions:
            v1_run = self.mlflow_models.client.get_run(existing_versions[-1].run_id)
            if str(v1_run.info.experiment_id) != str(mlflow_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Target registered name '{target.target_name}' is owned by another experiment"
                )
        
        promote_version = await self.mlflow_models.promote_model_version(
            src_name=name,
            src_version=version,
            dst_name=target.target_name,
            aliases=target.aliases,
        )

        version_info = await self._map_version(promote_version)

        return RegisteredModelVersionPromoteRead(
            registered_name=target.target_name,
            **version_info.dict(),
        )


    # Helpers

    async def _verify_ownership(
        self,
        name: str,
        mlflow_experiment_id: str,
    ) -> bool:
        versions = await self.mlflow_models.list_registered_model_versions(name)
        if not versions:
            return False
        
        run = None
        for v in versions:
            run = await self.mlflow_runs.get(v.run_id)
            if run:
                break
        
        return str(run.info.experiment_id) == str(mlflow_experiment_id) if run else False

    async def _is_version_from_exp(self, v, mlflow_exp_id):
        run = await self.mlflow_runs.get(v.run_id)

        return str(run.info.experiment_id) == str(mlflow_exp_id) if run else False

    async def _map_model(self, m, last_v=None):
        alias_list = [
            RegisteredModelAliasesRead(alias=k, version=v)
            for k, v in (m.aliases or {}).items()
        ]

        privacy = await self.experiment_registered_model_repo.get_privacy(model_name=m.name)

        return RegisteredModelRead(
            name=m.name,
            description=m.description,
            tags=m.tags or {},
            aliases=alias_list,
            latest_version=await self._map_version(last_v, m.aliases or {}) if last_v else None,
            is_private=privacy,
            created_at=datetime.fromtimestamp(m.creation_timestamp / 1000.0),
            updated_at=datetime.fromtimestamp(m.last_updated_timestamp / 1000.0),
        )

    async def _map_version(self, v, model_aliases_dict: Dict[str, str] = None):
        version_aliases = v.aliases if hasattr(v, 'aliases') and v.aliases else []
        if model_aliases_dict:
            version_aliases = [alias for alias, ver in model_aliases_dict.items() if str(ver) == str(v.version)]

        run_data = {"params": {}, "metrics": {}}
        if v.run_id:
            run = await self.mlflow_runs.get(v.run_id)
            if run:
                run_data["params"] = run.data.params
                run_data["metrics"] = run.data.metrics

        model_id = v.model_id
        if not model_id:
            match = re.search(r'(m-[a-f0-9]+)', v.source)
            model_id = match.group(1) if match else model_id

        return RegisteredModelVersionRead(
            version=v.version,
            description=v.description,
            status=v.status,
            run_id=v.run_id,
            model_id=model_id,
            tags=v.tags or {},
            params=run_data["params"],
            metrics=run_data["metrics"],
            aliases=version_aliases,
            created_at=datetime.fromtimestamp(v.creation_timestamp / 1000.0),
            updated_at=datetime.fromtimestamp(v.last_updated_timestamp / 1000.0),
        )

    def _map_version_detail(self, base: RegisteredModelVersionRead, info):
        detail_data = base.dict()
        
        if info:
            signature = None
        if info.signature:
            sig_raw = info.signature.to_dict()
            signature = {
                k: (json.loads(v) if isinstance(v, str) else v) 
                for k, v in sig_raw.items()
            }

            detail_data.update({
                "flavors": [f for f in (info.flavors or {}).keys()],
                "metadata": info.metadata,
                "signature": signature,
                "saved_input_example_info": info.saved_input_example_info,
            })
        return RegisteredModelVersionDetailRead(**detail_data)
