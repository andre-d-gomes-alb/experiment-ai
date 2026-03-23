from typing import Dict, List, Optional
from json import dumps

from app.core.config import settings
from .http import airflow_request


class AirflowConnections:
    def __init__(self):
        self.base = settings.AIRFLOW_API_BASE_URL

    async def create(
        self,
        *,
        connection_id: str,
        conn_type: str,
        description: Optional[str] = None,
        host: Optional[str] = None,
        login: Optional[str] = None,
        schema: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> Dict:
        payload = {
            "connection_id": connection_id,
            "conn_type": conn_type,
            "description": description,
            "host": host,
            "login": login,
            "schema": schema,
            "port": port,
            "password": password,
            "extra": dumps(extra) if extra is not None else "{}",
        }
        return await airflow_request(
            "POST",
            f"{self.base}/api/v2/connections",
            json=payload,
        )

    async def list(
        self,
        connection_id_pattern: Optional[str] = None,
    ) -> List[Dict]:
        params = {}
        if connection_id_pattern:
            params["connection_id_pattern"] = connection_id_pattern
        data = await airflow_request(
            "GET",
            f"{self.base}/api/v2/connections",
            params=params,
        )
        return data.get("connections", [])

    async def get(
        self,
        connection_id: str,
    ) -> Dict:
        return await airflow_request(
            "GET",
            f"{self.base}/api/v2/connections/{connection_id}",
        )

    async def update(
        self,
        *,
        connection_id: str,
        conn_type: str,
        description: Optional[str] = None,
        host: Optional[str] = None,
        login: Optional[str] = None,
        schema: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> Dict:
        payload = {"connection_id": connection_id}

        if conn_type is not None:
            payload["conn_type"] = conn_type
        if description is not None:
            payload["description"] = description
        if host is not None:
            payload["host"] = host
        if login is not None:
            payload["login"] = login
        if schema is not None:
            payload["schema"] = schema
        if port is not None:
            payload["port"] = port
        if password is not None:
            payload["password"] = password
        if extra is not None:
            payload["extra"] = dumps(extra)

        return await airflow_request(
            "PATCH",
            f"{self.base}/api/v2/connections/{connection_id}",
            json=payload,
        )

    async def delete(
        self,
        connection_id: str,
    ):
        await airflow_request(
            "DELETE",
            f"{self.base}/api/v2/connections/{connection_id}",
        )

    async def test(
        self,
        *,
        connection_id: str,
        conn_type: str,
        description: Optional[str] = None,
        host: Optional[str] = None,
        login: Optional[str] = None,
        schema: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> Dict:
        payload = {
            "connection_id": connection_id,
            "conn_type": conn_type,
            "description": description,
            "host": host,
            "login": login,
            "schema": schema,
            "port": port,
            "password": password,
            "extra": dumps(extra) if extra is not None else "{}",
        }
        return await airflow_request(
            "POST",
            f"{self.base}/api/v2/connections/test",
            json=payload,
        )
