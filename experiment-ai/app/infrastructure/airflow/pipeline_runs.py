from typing import Dict, List, Optional
from datetime import datetime, timezone

from app.core.config import settings
from .http import airflow_request


class AirflowPipelineRuns:
    def __init__(self):
        self.base = settings.AIRFLOW_API_BASE_URL
    
    async def trigger(
        self,
        *,
        dag_id: str,
        conf: Optional[dict] = None,
        logical_date: Optional[datetime] = None,
    ) -> Dict:
        if logical_date is None:
            logical_date = datetime.now(timezone.utc)

        payload = {
            "logical_date": logical_date.isoformat()
        }

        if conf is not None:
            payload["conf"] = conf

        return await airflow_request(
            "POST",
            f"{self.base}/api/v2/dags/{dag_id}/dagRuns",
            json=payload,
        )

    async def list(
        self,
        *,
        dag_id: str,
        limit: int,
    ) -> List[Dict]:
        data = await airflow_request(
            "GET",
            f"{self.base}/api/v2/dags/{dag_id}/dagRuns",
            params={
                "limit": limit,
                "order_by": [
                    "-logical_date",
                    "-start_date",
                    "-run_after",
                ],
            },
        )
        return data.get("dag_runs", [])

    async def get(
        self,
        *,
        dag_id: str,
        run_id: str,
    ) -> Dict:
        return await airflow_request(
            "GET",
            f"{self.base}/api/v2/dags/{dag_id}/dagRuns/{run_id}",
        )

    async def delete(
        self,
        *,
        dag_id: str,
        run_id: str,
    ):
        await airflow_request(
            "DELETE",
            f"{self.base}/api/v2/dags/{dag_id}/dagRuns/{run_id}",
        )

    async def list_task_instances(
        self,
        *,
        dag_id: str,
        run_id: str,
    ) -> List[Dict]:
        data = await airflow_request(
            "GET",
            f"{self.base}/api/v2/dags/{dag_id}/dagRuns/{run_id}/taskInstances",
            params={
                "order_by": [
                    "start_date",
                ],
            },
        )
        return data.get("task_instances", [])
    
    async def get_task_instance_log(
        self, 
        dag_id: str, 
        run_id: str, 
        task_id: str, 
        try_number: int,
    ) -> Dict:
        return await airflow_request(
            "GET",
            f"{self.base}/api/v2/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}"
        )
