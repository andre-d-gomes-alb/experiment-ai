from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.application.experiments import (
    ExperimentService, ExperimentMembersService,
    ExperimentVariablesService, ExperimentConnectionsService, ExperimentPipelinesService,
    ExperimentRunsService, ExperimentLoggedModelsService, ExperimentRegisteredModelsService,
)
from app.infrastructure.db.repositories import (
    ExperimentRepository, ExperimentMemberRepository, UserRepository, ExperimentRegisteredModelRepository,
    ExperimentVariableRepository, ExperimentConnectionRepository, ExperimentPipelineRepository,
)
from app.infrastructure.mlflow import (
    MlflowExperimentService, MlflowExperimentRunService,
    MlflowExperimentLoggedModelService, MlflowExperimentRegisteredModelService,
)
from app.infrastructure.airflow import AirflowVariables, AirflowConnections, AirflowPipelines, AirflowPipelineRuns


def get_experiment_service(
    session: AsyncSession = Depends(get_db),
) -> ExperimentService:
    return ExperimentService(
        experiment_repo=ExperimentRepository(session),
        variable_repo=ExperimentVariableRepository(session),
        connection_repo=ExperimentConnectionRepository(session),
        pipeline_repo=ExperimentPipelineRepository(session),
        mlflow_experiments=MlflowExperimentService(),
        mlflow_runs=MlflowExperimentRunService(),
        airflow_variables=AirflowVariables(),
        airflow_connections=AirflowConnections(),
        airflow_pipelines=AirflowPipelines(),
        mlflow_logged_models=MlflowExperimentLoggedModelService(),
        mlflow_registered_models=MlflowExperimentRegisteredModelService(),
    )

def get_experiment_members_service(
    session: AsyncSession = Depends(get_db),
) -> ExperimentMembersService:
    return ExperimentMembersService(
        experiment_repo=ExperimentRepository(session),
        member_repo=ExperimentMemberRepository(session),
        user_repo=UserRepository(session),
    )

def get_experiment_variables_service(
    session: AsyncSession = Depends(get_db),
) -> ExperimentVariablesService:
    return ExperimentVariablesService(
        experiment_repo=ExperimentRepository(session),
        variable_repo=ExperimentVariableRepository(session),
        airflow=AirflowVariables(),
    )

def get_experiment_connections_service(
    session: AsyncSession = Depends(get_db),
) -> ExperimentConnectionsService:
    return ExperimentConnectionsService(
        experiment_repo=ExperimentRepository(session),
        connection_repo=ExperimentConnectionRepository(session),
        airflow=AirflowConnections(),
    )

def get_experiment_pipelines_service(
    session: AsyncSession = Depends(get_db),
) -> ExperimentPipelinesService:
    return ExperimentPipelinesService(
        experiment_repo=ExperimentRepository(session),
        pipeline_repo=ExperimentPipelineRepository(session),
        airflow_pipelines=AirflowPipelines(),
        airflow_runs=AirflowPipelineRuns(),
        mlflow_registered_models=MlflowExperimentRegisteredModelService(),
    )

def get_experiment_runs_service(
    session: AsyncSession = Depends(get_db),
) -> ExperimentRunsService:
    return ExperimentRunsService(
        experiment_repo=ExperimentRepository(session),
        mlflow_runs=MlflowExperimentRunService(),
    )

def get_experiment_logged_models_service(
    session: AsyncSession = Depends(get_db),
) -> ExperimentLoggedModelsService:
    return ExperimentLoggedModelsService(
        experiment_repo=ExperimentRepository(session),
        mlflow_models=MlflowExperimentLoggedModelService(),
        mlflow_registered_models=MlflowExperimentRegisteredModelService(),
    )

def get_experiment_registered_models_service(
    session: AsyncSession = Depends(get_db),
) -> ExperimentRegisteredModelsService:
    return ExperimentRegisteredModelsService(
        experiment_repo=ExperimentRepository(session),
        experiment_registered_model_repo=ExperimentRegisteredModelRepository(session),
        mlflow_experiments=MlflowExperimentService(),
        mlflow_runs=MlflowExperimentRunService(),
        mlflow_models=MlflowExperimentRegisteredModelService(),
    )
