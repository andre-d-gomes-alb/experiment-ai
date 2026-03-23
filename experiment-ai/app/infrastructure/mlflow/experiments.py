import logging
from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException

from app.core.error_handlers import ExternalDependencyError


logger = logging.getLogger(__name__)


class MlflowExperimentService:
    def __init__(self):
        self.client = MlflowClient()

    async def create(
        self,
        name: str,
        description: str | None,
        tags: dict | None,
    ) -> str:
        try:
            existing = self.client.search_experiments(
                filter_string=f"name = '{name}'",
                view_type=3
            )

            if existing:
                exp = existing[0]
                if exp.lifecycle_stage == "deleted":
                    self.client.restore_experiment(exp.experiment_id)
                    
                    await self.update(exp.experiment_id, None, description, tags)
                
                return str(exp.experiment_id)

            mlflow_tags = {str(k): str(v) for k, v in (tags or {}).items()}
            if description:
                mlflow_tags["mlflow.note.content"] = str(description)

            experiment_id = self.client.create_experiment(name=name, tags=mlflow_tags)
            return str(experiment_id)

        except Exception as e:
            logger.error(f"[MLflow] Error in create/restore for '{name}': {e}")
            raise ExternalDependencyError()

    async def get(
        self,
        experiment_id: str,
    ) -> dict | None:
        try:
            exp = self.client.get_experiment(experiment_id)
            return {
                "id": exp.experiment_id,
                "name": exp.name,
                "description": exp.tags.get("mlflow.note.content"),
                "tags": {k: v for k, v in exp.tags.items() if not k.startswith("mlflow.")},
                "lifecycle_stage": exp.lifecycle_stage,
            }
        except MlflowException as e:
            if "RESOURCE_DOES_NOT_EXIST" in str(e):
                return None
            raise ExternalDependencyError()
        except Exception:
            raise ExternalDependencyError()

    async def list(self) -> list[dict]:
        try:
            experiments = self.client.search_experiments()
            return [
                {
                    "id": exp.experiment_id,
                    "name": exp.name,
                    "description": exp.tags.get("mlflow.note.content"),
                    "tags": {k: v for k, v in exp.tags.items() if not k.startswith("mlflow.")},
                    "lifecycle_stage": exp.lifecycle_stage,
                }
                for exp in experiments
            ]
        except Exception as e:
            logger.error(f"[MLflow] Failed to list experiments: {e}")
            raise ExternalDependencyError()
        
    async def update(
        self,
        experiment_id: str,
        name: str | None,
        description: str | None,
        tags: dict | None,
    ) -> None:
        try:
            if name:
                self.client.rename_experiment(experiment_id, name)
            
            if description is not None:
                self.client.set_experiment_tag(experiment_id, "mlflow.note.content", str(description))

            if tags is not None:
                current_exp = self.client.get_experiment(experiment_id)
                current_tags = current_exp.tags or {}

                for k in current_tags:
                    if k not in tags and not k.startswith("mlflow."):
                        self.client.delete_experiment_tag(experiment_id, k)

                for k, v in tags.items():
                    self.client.set_experiment_tag(experiment_id, str(k), str(v))

        except Exception as e:
            logger.error(f"[MLflow] Failed to update experiment {experiment_id}: {e}")
            raise ExternalDependencyError()

    async def delete(
        self,
        experiment_id: str,
    ) -> None:
        try:
            self.client.delete_experiment(experiment_id)
        except MlflowException as e:
            if "RESOURCE_DOES_NOT_EXIST" in str(e):
                return
            raise ExternalDependencyError()
        except Exception:
            raise ExternalDependencyError()
        
    async def ensure_active(
        self,
        experiment_id: str,
        name: str,
        description: str | None = None,
        tags: dict | None = None,
    ) -> str:
        try:
            exp = self.client.get_experiment(experiment_id)
            
            if exp.lifecycle_stage == "deleted":
                self.client.restore_experiment(experiment_id)
            
            await self.update(experiment_id, name, description, tags)
            return experiment_id

        except MlflowException as e:
            if "RESOURCE_DOES_NOT_EXIST" in str(e):
                return await self.create(name, description, tags)
            raise ExternalDependencyError()
