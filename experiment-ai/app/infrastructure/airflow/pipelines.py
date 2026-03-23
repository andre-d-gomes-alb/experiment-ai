from typing import Dict, List, Optional

from app.core.config import settings
from .http import airflow_request


class AirflowPipelines:
    def __init__(self):
        self.base = settings.AIRFLOW_API_BASE_URL

    async def list(
        self,
        pipeline_id_pattern: Optional[str] = None,
    ) -> List[Dict]:
        params = {}
        if pipeline_id_pattern:
            params["dag_id_pattern"] = pipeline_id_pattern

        data = await airflow_request(
            "GET",
            f"{self.base}/api/v2/dags",
            params=params,
        )
        return data.get("dags", [])

    async def get(
        self,
        dag_id: str,
    ) -> Dict:
        try:
            dag = await airflow_request(
                "GET",
                f"{self.base}/api/v2/dags/{dag_id}/details",
            )
        except Exception:
            return None
        
        if dag and ("detail" in dag or dag.get("is_stale", False)):
            return None
        
        return dag

    async def list_import_errors(
        self,
        *,
        filename_pattern: Optional[str] = None,
    ) -> List[Dict]:
        params = {}
        if filename_pattern:
            params["filename_pattern"] = filename_pattern

        data = await airflow_request(
            "GET",
            f"{self.base}/api/v2/importErrors",
            params=params,
        )
        return data.get("import_errors", [])

    async def get_assets(
        self,
        dag_ids: list,
    ) -> List[Dict]:
        data = await airflow_request(
            "GET",
            f"{self.base}/api/v2/assets",
            params={"dag_ids": ",".join(dag_ids)},
        )
        return data.get("assets", [])
    
    async def unpause(
        self,
        dag_id: str,
    ) -> Dict:
        return await airflow_request(
            "PATCH",
            f"{self.base}/api/v2/dags/{dag_id}",
            json={"is_paused": False},
        )

    async def pause(
        self,
        dag_id: str,
    ) -> Dict:
        return await airflow_request(
            "PATCH",
            f"{self.base}/api/v2/dags/{dag_id}",
            json={"is_paused": True},
        )
    
    async def delete(
        self,
        dag_id: str,
    ) -> None:
        await airflow_request(
            "DELETE",
            f"{self.base}/api/v2/dags/{dag_id}",
        )
