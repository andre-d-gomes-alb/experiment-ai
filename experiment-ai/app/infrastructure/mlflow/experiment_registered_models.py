from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException
from typing import Dict, List, Any
import mlflow
import logging
import io
import os
import tempfile
import zipfile
import gc
import pandas as pd

from app.core.error_handlers import ExternalDependencyError


logger = logging.getLogger(__name__)


class MlflowExperimentRegisteredModelService:
    def __init__(self):
        self.client = MlflowClient()
        self._model_cache = {}

    async def list_registered_models(self):
        try:
            return self.client.search_registered_models()
        except Exception as e:
            logger.error(f"[MLflow] Failed to search registered models: {e}")
            raise ExternalDependencyError()

    async def get_registered_model(
        self,
        name: str,
    ):
        try:
            return self.client.get_registered_model(name)
        except MlflowException as e:
            if "RESOURCE_DOES_NOT_EXIST" in str(e):
                return None
            raise ExternalDependencyError()
        except Exception as e:
            logger.error(f"[MLflow] Error retrieving registered model {name}: {e}")
            raise ExternalDependencyError()

    async def update_registered_model(
        self,
        name: str,
        new_name: str = None,
        description: str = None,
        tags: dict = None,
    ):
        try:
            current_name = name
            if new_name and new_name != name:
                self.client.rename_registered_model(name, new_name)
                current_name = new_name
            
            if description is not None:
                self.client.update_registered_model(current_name, description)
            
            if tags is not None:
                current_m = self.client.get_registered_model(current_name)
                for k in (current_m.tags or {}):
                    if k not in tags and not k.startswith("mlflow."):
                        self.client.delete_registered_model_tag(current_name, k)
                for k, v in tags.items():
                    if not k.startswith("mlflow."):
                        self.client.set_registered_model_tag(current_name, k, str(v))
            
            return self.client.get_registered_model(current_name)
        except Exception as e:
            logger.error(f"[MLflow] Error updating registered model {name}: {e}")
            raise ExternalDependencyError()

    async def delete_registered_model(
        self,
        name: str,
    ):
        try:
            self.client.delete_registered_model(name)
        except Exception as e:
            logger.error(f"[MLflow] Error deleting registered model {name}: {e}")
            raise ExternalDependencyError()
    

    # VERSIONS

    async def list_registered_model_versions(
        self,
        name: str,
    ):
        try:
            return self.client.search_model_versions(f"name='{name}'")
        except MlflowException as e:
            if any(keyword in str(e) for keyword in ["RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE"]):
                return None
            raise ExternalDependencyError()
        except Exception as e:
            logger.error(f"[MLflow] Error listing versions for {name}: {e}")
            raise ExternalDependencyError()

    async def get_registered_model_version(
        self,
        name: str,
        version: str,
    ):
        try:
            if version.isdigit():
                return self.client.get_model_version(name, version)
            else:
                return self.client.get_model_version_by_alias(name, version)
        except MlflowException as e:
            if any(keyword in str(e) for keyword in ["RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE"]):
                return None
            raise ExternalDependencyError()
        except Exception as e:
            logger.error(f"[MLflow] Error getting version {version} of {name}: {e}")
            raise ExternalDependencyError()
    
    async def get_registered_model_version_info(
        self,
        name: str,
        version: str,
    ):
        try:
            if not version.isdigit():
                model_uri = f"models:/{name}@{version}"
            else:
                model_uri = f"models:/{name}/{version}"
                
            return mlflow.models.get_model_info(model_uri)
        except Exception as e:
            logger.warning(f"[MLflow] Could not retrieve model info for {name}/{version}: {e}")
            return None

    async def update_registered_model_version(
        self,
        name: str,
        version: str,
        description: str = None,
        tags: dict = None,
        aliases: list = None,
    ):
        try:
            if description is not None:
                self.client.update_model_version(name, version, description)
            if tags is not None:
                current_v = self.client.get_model_version(name, version)
                for k in (current_v.tags or {}):
                    if k not in tags and not k.startswith("mlflow."):
                        self.client.delete_model_version_tag(name, version, k)
                for k, v in tags.items():
                    if not k.startswith("mlflow."):
                        self.client.set_model_version_tag(name, version, k, str(v))
            if aliases is not None:
                current_v = self.client.get_model_version(name, version)
                existing_aliases = current_v.aliases if hasattr(current_v, 'aliases') else []
                for alias in existing_aliases:
                    self.client.delete_registered_model_alias(name, alias)
                for alias in aliases:
                    self.client.set_registered_model_alias(name, alias, version)
            
            return self.client.get_model_version(name, version)
        except Exception as e:
            logger.error(f"[MLflow] Error updating version {version} of {name}: {e}")
            raise ExternalDependencyError()

    async def delete_model_version(
        self,
        name: str,
        version: str,
    ):
        try:
            self.client.delete_model_version(name, version)
        except Exception as e:
            logger.error(f"[MLflow] Error deleting version {version} of {name}: {e}")
            raise ExternalDependencyError()
        
    async def download_model_version_as_zip(
        self,
        model_uri: str,
    ) -> io.BytesIO:
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = mlflow.artifacts.download_artifacts(artifact_uri=model_uri, dst_path=tmp_dir)
            
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
        
    async def promote_model_version(
        self,
        src_name: str,
        src_version: str,
        dst_name: str,
        aliases: list = None,
    ):
        try:
            if not src_version.isdigit():
                model_uri = f"models:/{src_name}@{src_version}"
            else:
                model_uri = f"models:/{src_name}/{src_version}"
            
            promote = self.client.copy_model_version(model_uri, dst_name)

            for alias in aliases:
                self.client.set_registered_model_alias(dst_name, alias, promote.version)
        
            return self.client.get_model_version(dst_name, promote.version)
        except Exception as e:
            logger.error(f"[MLflow] Error promoting version {src_version} of {src_name}: {e}")
            raise ExternalDependencyError()
    
    async def predict_pyfunc_model(
        self,
        name: str,
        version: str,
        data: List[Dict[str, Any]],
    ):
        logging.getLogger("mlflow.utils.requirements_utils").setLevel(logging.CRITICAL)
        logging.getLogger("mlflow.pyfunc").setLevel(logging.CRITICAL)

        model = None
        if not version.isdigit():
            model_uri = f"models:/{name}@{version}"
        else:
            model_uri = f"models:/{name}/{version}"

        try:
            model = mlflow.pyfunc.load_model(model_uri)
            
            df = pd.DataFrame(data)
            predictions = model.predict(df)
            
            return predictions.tolist() if hasattr(predictions, "tolist") else predictions
        except Exception as e:
            logger.error(f"[MLflow] Prediction error for {model_uri}: {e}")
            raise e
        finally:
            if model:
                del model
            gc.collect()
