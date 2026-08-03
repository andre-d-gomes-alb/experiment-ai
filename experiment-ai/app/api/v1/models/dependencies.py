from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.application.models import ModelService
from app.infrastructure.db.repositories import ExperimentRepository, ExperimentRegisteredModelRepository
from app.infrastructure.mlflow import (
    MlflowExperimentService, MlflowExperimentRunService, MlflowExperimentRegisteredModelService,
)


def get_models_service(
    session: AsyncSession = Depends(get_db),
) -> ModelService:
    return ModelService(
        experiment_repo=ExperimentRepository(session),
        experiment_registered_model_repo=ExperimentRegisteredModelRepository(session),
        mlflow_experiments=MlflowExperimentService(),
        mlflow_runs=MlflowExperimentRunService(),
        mlflow_models=MlflowExperimentRegisteredModelService(),
    )
