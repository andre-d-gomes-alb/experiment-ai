from typing import Any, Dict, List

from app.core.config import settings
from .http import airflow_request


class AirflowVariables:
    def __init__(self):
        self.base = settings.AIRFLOW_API_BASE_URL

    async def create(
        self,
        *,
        key: str,
        value: Any,
        description: str | None,
    ):
        return await airflow_request(
            "POST",
            f"{self.base}/api/v2/variables",
            json={
                "key": key,
                "value": value,
                "description": description,
            },
        )

    async def list(self) -> List[Dict]:
        data = await airflow_request(
            "GET",
            f"{self.base}/api/v2/variables",
        )
        return data["variables"]

    async def get(
        self,
        key: str,
    ) -> Dict:
        return await airflow_request(
            "GET",
            f"{self.base}/api/v2/variables/{key}",
        )

    async def update(
        self,
        *,
        key: str,
        value: Any,
        description: str | None = None,
    ):
        payload = {"key": key, "value": value}
        if description is not None:
            payload["description"] = description

        return await airflow_request(
            "PATCH",
            f"{self.base}/api/v2/variables/{key}",
            json=payload,
        )

    async def delete(
        self,
        key: str,
    ):
        await airflow_request(
            "DELETE",
            f"{self.base}/api/v2/variables/{key}",
        )
