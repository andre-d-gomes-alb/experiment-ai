from typing import List, Optional
from httpx import HTTPStatusError
from datetime import datetime, timezone
import os

from app.infrastructure.db.repositories import (
    ExperimentRepository, ExperimentVariableRepository, ExperimentConnectionRepository, ExperimentPipelineRepository,
)
from app.infrastructure.mlflow import MlflowExperimentService
from app.infrastructure.airflow import AirflowVariables, AirflowConnections, AirflowPipelines, AirflowDagFileWriter
from app.core.resource_keys import experiment_resource_prefix, experiment_resource_key, experiment_prefix
from app.infrastructure.db.models import (
    User, Experiment, ExperimentVariable, ExperimentConnection, ExperimentPipeline,
)
from app.domain.experiments import ExperimentPipelineStatusEnum


# Reconciliation Functions for Experiment

async def reconcile_experiments(
    *,
    current_user: User,
    mlflow_experiments: MlflowExperimentService,
    experiment_repo: ExperimentRepository,
) -> list[Experiment]:
    prefix = experiment_prefix()
    exps = await experiment_repo.search_for_user(user_id=current_user.id, include_archived=True)
    experiments_db = [exp for exp, _ in exps]
    all_mlflow = await mlflow_experiments.list()
    
    mlflow_map = {str(m["id"]): m for m in all_mlflow}

    db_mlflow_ids = {str(e.mlflow_experiment_id) for e in experiments_db if e.mlflow_experiment_id}
    
    for m in all_mlflow:
        m_id = str(m["id"])
        if m["name"].startswith(prefix) and m_id not in db_mlflow_ids:
            await mlflow_experiments.delete(m_id)
            if m_id in mlflow_map:
                del mlflow_map[m_id]

    for exp_db in experiments_db:
        if exp_db.archived_at:
            continue

        exp_mlflow = mlflow_map.get(str(exp_db.mlflow_experiment_id)) if exp_db.mlflow_experiment_id else None
        
        if not exp_mlflow:
            await experiment_repo.archive(exp_db.id)
            exp_db.archived_at = datetime.now() 
            continue

        tech_name = f"{prefix}{exp_db.id}"
        needs_sync = (
            exp_mlflow.get("name") != tech_name or
            exp_mlflow.get("description") != exp_db.description or
            exp_mlflow.get("tags") != exp_db.tags
        )
        
        if needs_sync:
            await mlflow_experiments.update(
                experiment_id=exp_mlflow["id"],
                name=tech_name,
                description=exp_db.description,
                tags=exp_db.tags,
            )

    return experiments_db

async def reconcile_experiment(
    experiment_id: str,
    experiment_repo: ExperimentRepository,
    mlflow_experiments: MlflowExperimentService,
) -> Optional[Experiment]:
    exp_db = await experiment_repo.get_by_id(experiment_id)
    if not exp_db:
        return None
    
    if exp_db.archived_at:
        if exp_db.mlflow_experiment_id:
            try:
                await mlflow_experiments.delete(str(exp_db.mlflow_experiment_id))
            except Exception:
                pass
        return exp_db
    
    if not exp_db.mlflow_experiment_id:
        exp_db = await experiment_repo.archive(experiment_id)
        return exp_db
        
    try:
        exp_mlflow = await mlflow_experiments.get(str(exp_db.mlflow_experiment_id))
        if exp_mlflow.get("lifecycle_stage") == "deleted":
            exp_mlflow = None
    except Exception:
        exp_mlflow = None

    if not exp_mlflow:
        exp_db = await experiment_repo.archive(experiment_id)
        if exp_db:
            exp_db.archived_at = datetime.now() 
        return exp_db
    
    prefix = experiment_prefix()
    tech_name = f"{prefix}{exp_db.id}"
    needs_sync = (
        exp_mlflow.get("name") != tech_name or
        exp_mlflow.get("description") != exp_db.description or
        exp_mlflow.get("tags") != exp_db.tags
    )

    if needs_sync:
        await mlflow_experiments.update(
            experiment_id=str(exp_db.mlflow_experiment_id),
            name=tech_name,
            description=exp_db.description,
            tags=exp_db.tags,
        )
        
    return exp_db


# Reconciliation Functions for Experiment Variables

async def reconcile_experiment_variables(
    experiment_id: str,
    airflow: AirflowVariables,
    variable_repo: ExperimentVariableRepository,
) -> List[ExperimentVariable]:
    prefix = experiment_resource_prefix(experiment_id)

    airflow_vars = await airflow.list()
    airflow_map = {
        v["key"].replace(prefix, ""): v
        for v in airflow_vars
        if v.get("key", "").startswith(prefix)
    }

    vars_db = await variable_repo.list(experiment_id=experiment_id)

    db_keys = {v.id for v in vars_db}
    airflow_keys = set(airflow_map.keys())

    for var in vars_db:
        af_var = airflow_map.get(var.id)
        if af_var is None:
            await variable_repo.delete(experiment_id, var.id)
            continue

        if (af_var.get("description") or "") != (var.description or ""):
            value = af_var.get("value")
            if value is not None:
                af_key = experiment_resource_key(experiment_id=experiment_id, resource_key=var.id)
                await airflow.update(
                    key=af_key,
                    value=value,
                    description=var.description,
                )

    for key in airflow_keys - db_keys:
        af_key = experiment_resource_key(experiment_id=experiment_id, resource_key=key)
        await airflow.delete(af_key)

    return await variable_repo.list(experiment_id=experiment_id)

async def reconcile_experiment_variable(
    experiment_id: str,
    id: str,
    airflow: AirflowVariables,
    variable_repo: ExperimentVariableRepository,
) -> Optional[ExperimentVariable]:
    af_key = experiment_resource_key(experiment_id=experiment_id, resource_key=id)

    try:
        af_var = await airflow.get(af_key)
        if af_var and "detail" in af_var and "not found" in af_var["detail"]:
            af_var = None
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            af_var = None
        else:
            raise

    var = await variable_repo.get(experiment_id, id)

    if var and af_var is not None:
        value = af_var.get("value")
        if value is not None and (af_var.get("description") or "") != (var.description or ""):
            await airflow.update(
                key=af_key,
                value=value,
                description=var.description,
            )
        return var

    if var and af_var is None:
        await variable_repo.delete(experiment_id, id)
        return None

    if af_var is not None and var is None:
        await airflow.delete(af_key)
        return None

    return None


# Reconciliation Functions for Experiment Connections

async def reconcile_experiment_connections(
    experiment_id: str,
    airflow: AirflowConnections,
    connection_repo: ExperimentConnectionRepository,
) -> List[ExperimentConnection]:
    prefix = experiment_resource_prefix(experiment_id)

    airflow_conns = await airflow.list(connection_id_pattern=f"{prefix}%")
    airflow_map = {
        c["connection_id"].replace(prefix, ""): c
        for c in airflow_conns
        if c.get("connection_id", "").startswith(prefix)
    }

    conns_db = await connection_repo.list(experiment_id=experiment_id)

    db_keys = {c.id for c in conns_db}
    airflow_keys = set(airflow_map.keys())

    for conn in conns_db:
        af_conn = airflow_map.get(conn.id)
        if af_conn is None:
            await connection_repo.delete(experiment_id, conn.id)
            continue

        if (af_conn.get("description") or "") != (conn.description or ""):
            af_key = f"{prefix}{conn.id}"
            await airflow.update(
                connection_id=af_key,
                conn_type=af_conn["conn_type"],
                description=conn.description,
            )

    for key in airflow_keys - db_keys:
        af_key = f"{prefix}{key}"
        await airflow.delete(af_key)

    return await connection_repo.list(experiment_id=experiment_id)

async def reconcile_experiment_connection(
    experiment_id: str,
    id: str,
    airflow: AirflowConnections,
    connection_repo: ExperimentConnectionRepository,
) -> Optional[ExperimentConnection]:
    af_key = f"{experiment_resource_prefix(experiment_id)}{id}"

    try:
        af_conn = await airflow.get(af_key)
        if af_conn and "detail" in af_conn and "not found" in af_conn["detail"]:
            af_conn = None
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            af_conn = None
        else:
            raise

    conn = await connection_repo.get(experiment_id, id)

    if conn and af_conn is not None:
        if (af_conn.get("description") or "") != (conn.description or ""):
            await airflow.update(
                connection_id=af_key,
                conn_type=af_conn["conn_type"],
                description=conn.description,
            )
        return conn

    if conn and af_conn is None:
        await connection_repo.delete(experiment_id, id)
        return None

    if af_conn is not None and conn is None:
        await airflow.delete(af_key)
        return None

    return None


# Reconciliation Function for Experiment Pipelines

async def reconcile_experiment_pipelines(
    *,
    experiment_id: str,
    pipeline_repo: ExperimentPipelineRepository,
    airflow: AirflowPipelines,
) -> List[ExperimentPipeline]:
    prefix = experiment_resource_prefix(experiment_id)
    writer = AirflowDagFileWriter()

    airflow_dags = await airflow.list(pipeline_id_pattern=f"{prefix}%")
    airflow_map = {d["dag_id"].replace(prefix, "", 1): d for d in airflow_dags}
    
    import_errors = await airflow.list_import_errors()
    error_pipeline_ids = set()
    for e in import_errors:
        filename = os.path.basename(e.get("filename", ""))
        if filename.startswith(prefix) and filename.endswith(".py"):
            pid = filename.removesuffix(".py").replace(prefix, "", 1)
            error_pipeline_ids.add(pid)

    pipelines_db = await pipeline_repo.list(experiment_id=experiment_id)
    db_ids = {p.id for p in pipelines_db}
    result: list[ExperimentPipeline] = []

    for pipeline in pipelines_db:
        af = airflow_map.get(pipeline.id)
        has_error = pipeline.id in error_pipeline_ids
        
        if not af and not has_error:
            if pipeline.status not in {ExperimentPipelineStatusEnum.CREATING, ExperimentPipelineStatusEnum.UPDATING}:
                await pipeline_repo.delete(experiment_id, pipeline.id)
                continue

        if has_error:
            if pipeline.status != ExperimentPipelineStatusEnum.ERROR:
                pipeline.status = ExperimentPipelineStatusEnum.ERROR
                await pipeline_repo.update(pipeline)
        
        elif af:
            is_paused = af.get("is_paused")
            changed = False

            if is_paused and pipeline.status != ExperimentPipelineStatusEnum.PAUSED:
                pipeline.status = ExperimentPipelineStatusEnum.PAUSED
                pipeline.paused_at = datetime.now(timezone.utc)
                changed = True
                
            elif not is_paused and pipeline.status != ExperimentPipelineStatusEnum.ACTIVE:
                pipeline.status = ExperimentPipelineStatusEnum.ACTIVE
                pipeline.paused_at = None
                changed = True
            
            if changed:
                await pipeline_repo.update(pipeline)

        result.append(pipeline)

    for pid in set(airflow_map.keys()) - db_ids:
        dag_id = f"{prefix}{pid}"
        writer.delete_pipeline(pipeline_id=dag_id)
        await airflow.delete(dag_id)

    for pid in error_pipeline_ids - db_ids:
        dag_id = f"{prefix}{pid}"
        writer.delete_pipeline(pipeline_id=dag_id)

    return result

async def reconcile_experiment_pipeline(
    *,
    experiment_id: str,
    id: str,
    pipeline_repo: ExperimentPipelineRepository,
    airflow: AirflowPipelines,
) -> Optional[ExperimentPipeline]:
    prefix = experiment_resource_prefix(experiment_id)
    dag_id = f"{prefix}{id}"
    target_file = f"{dag_id}.py"

    pipeline = await pipeline_repo.get(experiment_id, id)
    af = await airflow.get(dag_id)

    import_errors = await airflow.list_import_errors()
    has_error = any(
        os.path.basename(err.get("filename", "")) == target_file
        for err in import_errors
    )
    
    is_listed = af is not None
    is_paused = af.get("is_paused") if af else None

    if not pipeline:
        if has_error or is_listed:
            writer = AirflowDagFileWriter()
            writer.delete_pipeline(pipeline_id=dag_id)
            if is_listed:
                await airflow.delete(dag_id)
        return None

    if not is_listed and not has_error:
        if pipeline.status not in {
            ExperimentPipelineStatusEnum.CREATING,
            ExperimentPipelineStatusEnum.UPDATING
        }:
            await pipeline_repo.delete(experiment_id, id)
            return None
        return pipeline

    if has_error:
        if pipeline.status != ExperimentPipelineStatusEnum.ERROR:
            pipeline.status = ExperimentPipelineStatusEnum.ERROR
            await pipeline_repo.update(pipeline)
        return pipeline

    if is_listed:
        changed = False
        if is_paused is True and pipeline.status != ExperimentPipelineStatusEnum.PAUSED:
            pipeline.status = ExperimentPipelineStatusEnum.PAUSED
            pipeline.paused_at = datetime.now(timezone.utc)
            changed = True
        elif is_paused is False and pipeline.status != ExperimentPipelineStatusEnum.ACTIVE:
            pipeline.status = ExperimentPipelineStatusEnum.ACTIVE
            pipeline.paused_at = None
            changed = True
        
        if changed:
            await pipeline_repo.update(pipeline)
            
    return pipeline
