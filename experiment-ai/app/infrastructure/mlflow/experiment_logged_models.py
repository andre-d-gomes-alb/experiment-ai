import logging
from typing import Dict, Optional
import mlflow
from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException
import io
import os
import tempfile
import zipfile

from app.core.error_handlers import ExternalDependencyError


logger = logging.getLogger(__name__)


class MlflowExperimentLoggedModelService:
    def __init__(self):
        self.client = MlflowClient()

    async def list_logged_models(
        self,
        experiment_id: str,
        status_code: int,
    ):
        try:
            filter_str = f"status = {status_code}"
            return self.client.search_logged_models(
                experiment_ids=[experiment_id],
                filter_string=filter_str
            )
        except Exception as e:
            logger.error(
                f"[MLflow] Failed to search logged models (Exp: {experiment_id}, Status: {status_code}): {e}"
            )
            raise ExternalDependencyError()

    async def get_logged_model(
        self,
        model_id: str,
    ):
        try:
            return self.client.get_logged_model(model_id)
        except MlflowException as e:
            if any(keyword in str(e) for keyword in ["RESOURCE_DOES_NOT_EXIST", "Invalid value"]):
                return None
            raise ExternalDependencyError()
        except Exception as e:
            logger.error(f"[MLflow] Error retrieving logged model {model_id}: {e}")
            raise ExternalDependencyError()

    async def update_logged_model_metadata(
        self, 
        model_id: str, 
        status: Optional[str] = None, 
        tags: Optional[Dict[str, str]] = None,
    ):
        try:
            if status is not None:
                self.client.finalize_logged_model(model_id=model_id, status=status)
            
            if tags is not None:
                current_model = self.client.get_logged_model(model_id)
                current_tags = current_model.tags or {}

                for k in current_tags:
                    if k not in tags and not k.startswith("mlflow."):
                        self.client.delete_logged_model_tag(model_id, k)

                for k, v in tags.items():
                    if not str(k).startswith("mlflow."):
                        self.client.set_logged_model_tags(model_id, {str(k): str(v)})
        
        except MlflowException as e:
            logger.error(f"[MLflow] Mlflow error updating metadata for model {model_id}: {e}")
            raise ExternalDependencyError()
        
        except Exception as e:
            logger.error(f"[MLflow] Unexpected error updating model {model_id}: {e}")
            raise ExternalDependencyError()
        
    async def download_logged_model_as_zip(
        self,
        artifact_uri: str,
    ) -> io.BytesIO:
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = mlflow.artifacts.download_artifacts(artifact_uri=artifact_uri, dst_path=tmp_dir)
            if not os.path.exists(local_path) or not os.listdir(local_path):
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
        
    async def register_model(
        self, 
        model_uri: str, 
        name: str,
        run_id: str,
        model_id: str,
        description: str = None, 
        tags: dict = None, 
        aliases: list = None,
    ):
        logging.getLogger("mlflow.store.model_registry.abstract_store").setLevel(logging.CRITICAL)

        try:
            try:
                self.client.get_registered_model(name)
            except Exception as e:
                if "RESOURCE_DOES_NOT_EXIST" in str(e).upper():
                    self.client.create_registered_model(name)
                else:
                    raise e

            m_version = self.client.create_model_version(
                name=name,
                source=model_uri,
                run_id=run_id,
                model_id=model_id,
            )

            version_id = m_version.version

            if description is not None:
                self.client.update_model_version(name, version_id, description)

            if tags is not None:
                current_v = self.client.get_model_version(name, version_id)
                current_tags = current_v.tags or {}
                for k in current_tags:
                    if k not in tags and not k.startswith("mlflow."):
                        self.client.delete_model_version_tag(name, version_id, k)
                for k, v in tags.items():
                    if not k.startswith("mlflow."):
                        self.client.set_model_version_tag(name, version_id, k, str(v))

            if aliases is not None:
                for alias in aliases:
                    self.client.set_registered_model_alias(name, alias, version_id)

            return self.client.get_model_version(name, version_id)

        except Exception as e:
            logger.error(f"[MLflow] Error during register and update for {name}: {e}")
            raise ExternalDependencyError()
