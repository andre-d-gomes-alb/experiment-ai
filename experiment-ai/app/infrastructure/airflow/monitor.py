from app.core.config import settings
from .http import airflow_request


class AirflowMonitor:
    def __init__(self):
        self.base = settings.AIRFLOW_API_BASE_URL

    async def health(self):
        return await airflow_request(
            "GET",
            f"{self.base}/api/v2/monitor/health",
        )
