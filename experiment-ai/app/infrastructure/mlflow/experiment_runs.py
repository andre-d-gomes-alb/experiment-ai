import logging
import mlflow
from mlflow.tracking import MlflowClient
from mlflow.entities import ViewType
from mlflow.exceptions import MlflowException
import io
import zipfile
import tempfile
import os

from app.core.error_handlers import ExternalDependencyError


logger = logging.getLogger(__name__)


class MlflowExperimentRunService:
    def __init__(self):
        self.client = MlflowClient()

    async def list(
        self,
        experiment_id: str,
        view_type: int = ViewType.ACTIVE_ONLY,
    ):
        try:
            return self.client.search_runs(
                experiment_ids=[experiment_id],
                run_view_type=view_type
            )
        except Exception as e:
            logger.error(f"[MLflow] Failed to list runs for experiment {experiment_id}: {e}")
            raise ExternalDependencyError()

    async def get(
        self,
        run_id: str,
    ):
        try:
            return self.client.get_run(run_id)
        except MlflowException as e:
            if any(keyword in str(e) for keyword in ["RESOURCE_DOES_NOT_EXIST", "Invalid value"]):
                return None
            raise ExternalDependencyError()
        except Exception as e:
            logger.error(f"[MLflow] Error retrieving run {run_id}: {e}")
            raise ExternalDependencyError()

    async def list_artifacts(
        self,
        run_id: str,
        path: str = None,
    ):
        try:
            return self.client.list_artifacts(run_id, path=path)
        except Exception as e:
            logger.error(f"[MLflow] Error listing artifacts for run {run_id}: {e}")
            raise ExternalDependencyError()

    async def delete(
        self,
        run_id: str,
    ) -> None:
        try:
            self.client.delete_run(run_id)
        except MlflowException as e:
            if any(keyword in str(e) for keyword in ["RESOURCE_DOES_NOT_EXIST", "Invalid value"]):
                return
            raise ExternalDependencyError()
        except Exception:
            raise ExternalDependencyError()
        
    async def get_artifacts_as_zip(
        self,
        run_id: str,
    ) -> io.BytesIO:
        logging.getLogger("mlflow.store.artifact.artifact_repo").setLevel(logging.CRITICAL)

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = self.client.download_artifacts(run_id=run_id, path="", dst_path=tmp_dir)

            model_exists = any(f == "MLmodel" for root, _, files in os.walk(tmp_dir) for f in files)
            if not model_exists:
                try:
                    model_info = mlflow.models.get_model_info(f"runs:/{run_id}/model")
                    model_uri = model_info.model_uri
                    logged_model_dst = os.path.join(tmp_dir, "logged_model")
                    mlflow.artifacts.download_artifacts(artifact_uri=model_uri, dst_path=logged_model_dst)
                except Exception:
                    pass

            if not os.listdir(tmp_dir):
                return None
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(local_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, local_path)
                        zf.write(full_path, rel_path)
            
            zip_buffer.seek(0)

            return zip_buffer
