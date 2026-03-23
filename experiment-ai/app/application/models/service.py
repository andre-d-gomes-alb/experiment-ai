from fastapi import HTTPException, status
from typing import List, Dict
from datetime import datetime
import re
import json
from jinja2 import Environment, PackageLoader
import io
import zipfile
import time

from app.infrastructure.db.repositories import ExperimentRepository
from app.infrastructure.mlflow import (
    MlflowExperimentRegisteredModelService, MlflowExperimentRunService, MlflowExperimentService,
)
from app.api.v1.models import (
    ModelRead, ModelDetailRead, ModelAliasesRead, ModelVersionRead, ModelVersionDetailRead,
    ModelVersionInferenceRequest, ModelVersionInferenceResponse,
)


ALLOWED_SORT_FIELDS = {
    "name",
    "experiment_name",
    "created_at",
    "updated_at",
}

ALLOWED_VERSION_SORT_FIELDS = {
    "version",
    "created_at",
    "updated_at"
}


class ModelService:
    def __init__(
        self,
        experiment_repo: ExperimentRepository,
        mlflow_experiments: MlflowExperimentService,
        mlflow_runs: MlflowExperimentRunService,
        mlflow_models: MlflowExperimentRegisteredModelService
    ):
        self.experiment_repo = experiment_repo
        self.mlflow_ext = mlflow_experiments
        self.mlflow_runs = mlflow_runs
        self.mlflow_models = mlflow_models

    async def list_models(
        self,
        tags: str | None = None,
        aliases: str | None = None,
        experiment_name: str | None = None,
        only_experiment_models: bool = False,
        sort: str = "created_at desc",
    ) -> List[ModelRead]:
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
        exp_name_cache: Dict[str, str] = {}

        for m in all_models:
            latest = m.latest_versions[0] if m.latest_versions else None
            exp_name = None

            if latest and latest.run_id:
                exp_name = await self._resolve_db_experiment_name(latest.run_id, exp_name_cache)

            if only_experiment_models and not exp_name:
                continue
            
            if experiment_name and (not exp_name or experiment_name.lower() not in exp_name.lower()):
                continue

            mapped_model = await self._map_model(m, exp_name, latest)
            results.append(mapped_model)
        
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

            filtered.append(m)

        def get_sort_value(obj: ModelRead):
            val = getattr(obj, sort_field, None)
            return (val is None, val)

        filtered.sort(key=get_sort_value, reverse=(sort_order == "desc"))

        return filtered
    
    async def get_model(
        self,
        name: str
    ) -> ModelDetailRead:
        m = await self.mlflow_models.get_registered_model(name)
        if not m:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found",
            )

        latest_v = m.latest_versions[0] if m.latest_versions else None

        exp_name = None
        if latest_v and latest_v.run_id:
            exp_name = await self._resolve_db_experiment_name(latest_v.run_id, {})

        latest_detail = None
        if latest_v:
            base_v = await self._map_version(latest_v, m.aliases if m.aliases else {})
            model_info = await self.mlflow_models.get_registered_model_version_info(name, latest_v.version)
            latest_detail = self._map_version_detail(base_v, model_info)

        return ModelDetailRead(
            name=m.name,
            description=m.description,
            tags=m.tags or {},
            aliases=[
                ModelAliasesRead(alias=k, version=v)
                for k, v in (m.aliases or {}).items()
            ],
            latest_version=latest_detail,
            experiment_name=exp_name,
            created_at=datetime.fromtimestamp(m.creation_timestamp / 1000.0),
            updated_at=datetime.fromtimestamp(m.last_updated_timestamp / 1000.0),
        )
    

    # VERSIONS

    async def list_model_versions(
        self,
        name: str,
        tags: str | None = None,
        params: str | None = None,
        metrics: str | None = None,
        aliases: str | None = None,
        sort: str = "version desc",
    ) -> List[ModelVersionRead]:
        model_obj = await self.mlflow_models.get_registered_model(name)
        if not model_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found",
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
        
        versions = []
        for rv in raw_versions:
            if rv.status.upper() != "READY":
                continue

            versions.append(await self._map_version(rv, model_obj.aliases if model_obj.aliases else []))

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

        def get_sort_value(obj: ModelVersionRead):
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
    
    async def get_model_version(
        self,
        name: str,
        version: str,
    ) -> ModelVersionDetailRead:
        model_obj = await self.mlflow_models.get_registered_model(name)
        if not model_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found",
            )
        
        m_version = await self.mlflow_models.get_registered_model_version(name, version)
        if not m_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model version not found"
            )
        
        base_read = await self._map_version(m_version)
        model_info = await self.mlflow_models.get_registered_model_version_info(name, m_version.version)
        
        return self._map_version_detail(base_read, model_info)
    
    async def download_model_version_zip(
        self,
        name: str,
        version: str,
    ):
        model_obj = await self.mlflow_models.get_registered_model(name)
        if not model_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found",
            )
        
        m_version = await self.mlflow_models.get_registered_model_version(name, version)
        if not m_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model version not found"
            )
        
        zip_buffer = await self.mlflow_models.download_model_version_as_zip(m_version.source)
        if not zip_buffer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="No artifacts found for this model"
            )
        
        run = await self.mlflow_runs.get(m_version.run_id) if m_version.run_id else None
        exp_name = await self._resolve_db_experiment_name(m_version.run_id, {}) if m_version.run_id else "None"
        model_info = await self.mlflow_models.get_registered_model_version_info(name, m_version.version)
        
        template_data = self._prepare_readme_data(model_obj, m_version, model_info, run, exp_name)
        readme_content = self._render_readme(template_data)
        final_zip_buffer = self._inject_readme_to_zip(zip_buffer, readme_content)
        
        filename = f"model__{name}__v{m_version.version}.zip"
        
        return final_zip_buffer, filename
    
    async def model_version_make_prediction(
        self, 
        name: str, 
        version: str, 
        data: ModelVersionInferenceRequest,
    ) -> ModelVersionInferenceResponse:
        model_obj = await self.mlflow_models.get_registered_model(name)
        if not model_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found",
            )
        
        m_version = await self.mlflow_models.get_registered_model_version(name, version)
        if not m_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model version not found"
            )
        
        model_info = await self.mlflow_models.get_registered_model_version_info(name, m_version.version)
        flavors = [f for f in (model_info.flavors or {}).keys()]
        if "python_function" not in flavors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Model version not suppoted"
            )

        try:
            start_data = datetime.utcnow()
            start_time = time.perf_counter()
            preds = await self.mlflow_models.predict_pyfunc_model(name, version, data.dataframe_records)
            latency = round(time.perf_counter() - start_time, 4)

            if not isinstance(preds, list):
                if hasattr(preds, "tolist"):
                    preds = preds.tolist()
                else:
                    preds = [preds]
            
            return ModelVersionInferenceResponse(
                predictions=preds,
                latency_seconds=latency,
                predicted_at=start_data
            )
        except Exception as e:
            sig_raw = model_info.signature.to_dict() if model_info and model_info.signature else {}
            if sig_raw:
                signature = {
                    k: (json.loads(v) if isinstance(v, str) else v) 
                    for k, v in sig_raw.items()
                }
            else:
                signature = "No signature defined"

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "Prediction failed",
                    "reason": str(e),
                    "expected_schema": signature
                }
            )
    

    # Helpers

    async def _resolve_db_experiment_name(self, run_id: str, cache: Dict[str, str]) -> str:
        try:
            run = await self.mlflow_runs.get(run_id)
            if not run:
                return None
            
            mlflow_id = str(run.info.experiment_id)
            if mlflow_id in cache:
                return cache[mlflow_id]

            exp_db = await self.experiment_repo.get_by_mlflow_id(int(mlflow_id))
            final_name = exp_db.name if exp_db else None
            cache[mlflow_id] = final_name
            return final_name
        except Exception as e:
            return None

    async def _map_model(self, m, exp_name, last_v=None):
        alias_list = [
            ModelAliasesRead(alias=k, version=v)
            for k, v in (m.aliases or {}).items()
        ]
        return ModelRead(
            name=m.name,
            description=m.description,
            tags=m.tags or {},
            aliases=alias_list,
            latest_version=await self._map_version(last_v, m.aliases or {}) if last_v else None,
            experiment_name=exp_name,
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

        return ModelVersionRead(
            version=v.version,
            description=v.description,
            tags=v.tags or {},
            params=run_data["params"],
            metrics=run_data["metrics"],
            aliases=version_aliases,
            created_at=datetime.fromtimestamp(v.creation_timestamp / 1000.0),
            updated_at=datetime.fromtimestamp(v.last_updated_timestamp / 1000.0),
        )
    
    def _map_version_detail(self, base: ModelVersionRead, info):
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

        return ModelVersionDetailRead(**detail_data)
    
    def _prepare_readme_data(self, m_obj, v_obj, info, run, exp_name):
        input_cols = []
        output_cols = []
        input_example = None

        if info:
            if info.signature:
                sig_raw = info.signature.to_dict()
                signature = {
                    k: (json.loads(v) if isinstance(v, str) else v) 
                    for k, v in sig_raw.items()
                }
                
                input_cols = [
                    i for i in signature.get('inputs', []) 
                    if isinstance(i, dict)
                ]
                output_cols = [
                    o for o in signature.get('outputs', []) 
                    if isinstance(o, dict)
                ]

            if info.saved_input_example_info:
                ex = info.saved_input_example_info
                input_example = json.loads(ex) if isinstance(ex, str) else ex

        all_flavors = list((info.flavors or {}).keys()) if info else []

        latest_v = v_obj.version
        if hasattr(m_obj, 'latest_versions') and m_obj.latest_versions:
            latest_v = m_obj.latest_versions[0].version

        return {
            "m_name": m_obj.name,
            "m_version": v_obj.version,
            "m_description": m_obj.description,
            "m_tags": m_obj.tags,
            "m_latest_version": latest_v,
            "m_experiment_name": exp_name,
            "m_created_at": datetime.fromtimestamp(m_obj.creation_timestamp / 1000.0).strftime('%Y-%m-%d %H:%M'),
            "m_updated_at": datetime.fromtimestamp(m_obj.last_updated_timestamp / 1000.0).strftime('%Y-%m-%d %H:%M'),
            
            "v_description": v_obj.description,
            "v_tags": v_obj.tags,
            "v_params": run.data.params if run else {},
            "v_metrics": run.data.metrics if run else {},
            "v_aliases": getattr(v_obj, 'aliases', []),
            "v_flavors": all_flavors,
            "v_metadata": info.metadata if info else {},
            "v_created_at": datetime.fromtimestamp(v_obj.creation_timestamp / 1000.0).strftime('%Y-%m-%d %H:%M'),
            "v_updated_at": datetime.fromtimestamp(v_obj.last_updated_timestamp / 1000.0).strftime('%Y-%m-%d %H:%M'),
            
            "input_columns": input_cols,
            "output_columns": output_cols,
            "input_example": input_example
        }
    
    def _render_readme(self, data):
        env = Environment(
            loader=PackageLoader("app.infrastructure.mlflow", "model_templates")
        )
        template = env.get_template("readme_model_template.jinja")
        return template.render(**data)

    def _inject_readme_to_zip(self, original_buffer, readme_content):
        original_buffer.seek(0)
        new_buffer = io.BytesIO()
        
        with zipfile.ZipFile(original_buffer, 'r') as zip_read:
            with zipfile.ZipFile(new_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_write:
                for item in zip_read.infolist():
                    zip_write.writestr(item, zip_read.read(item.filename))
                
                zip_write.writestr("README.md", readme_content)
        
        new_buffer.seek(0)
        return new_buffer
