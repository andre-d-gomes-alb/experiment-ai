import httpx
import logging
from typing import Any

from .auth import AirflowAuth
from app.core.error_handlers import ExternalDependencyError


logger = logging.getLogger(__name__)


async def airflow_request(
    method: str,
    url: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
) -> Any:
    token = await AirflowAuth.get_token()

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=json,
            params=params,
        )

        if resp.status_code == 401:
            # Token expired or invalid, refresh and retry
            AirflowAuth.invalidate()
            token = await AirflowAuth.get_token(force_refresh=True)

            resp = await client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=json,
                params=params,
            )
        
        if resp.status_code >= 400 and resp.status_code != 404:
            logger.error(f"[Airflow API] Request failed: {resp.text}")
            raise ExternalDependencyError()

        return resp.json() if resp.content else None
