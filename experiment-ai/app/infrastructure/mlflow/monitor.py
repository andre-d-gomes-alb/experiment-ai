import logging
from mlflow.tracking import MlflowClient


logger = logging.getLogger(__name__)


class MlflowMonitor:
    def __init__(self):
        self.client = MlflowClient()

    def health(self) -> bool:
        try:
            self.client.search_experiments()
            return True
        except Exception as e:
            logger.error(f"[MLflow] Health check failed: {e}")
            return False
