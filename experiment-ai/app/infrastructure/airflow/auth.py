import httpx
import logging
from fastapi import HTTPException, status

from app.core.config import settings


logger = logging.getLogger(__name__)


class AirflowAuth:
    _token: str | None = None

    @classmethod
    async def get_token(
        cls,
        *,
        force_refresh: bool = False,
    ) -> str:
        if cls._token and not force_refresh:
            return cls._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.AIRFLOW_API_BASE_URL}/auth/token",
                json={
                    "username": settings.AIRFLOW_USERNAME,
                    "password": settings.AIRFLOW_PASSWORD,
                },
            )

            if resp.status_code >= 400:
                logger.error(f"[Airflow API] Auth failed: {resp.text}")

                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failure of an internal dependency. Please contact platform support.",
                )

            cls._token = resp.json()["access_token"]
            return cls._token

    @classmethod
    def invalidate(cls):
        cls._token = None
