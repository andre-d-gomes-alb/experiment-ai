from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.application.monitor import MonitorService
from app.api.v1.monitor import MonitorResponse
from app.infrastructure.db.models import User
from app.core.enums import UserRoleEnum
from app.core.security import get_authenticated_user, validate_internal_health_token


router = APIRouter()


@router.get("/health", response_model=MonitorResponse)
async def check_health(
    request: Request,
    current_user: User | None = Depends(get_authenticated_user),
):
    # Internal health token for helm chart test
    internal_health_token = request.headers.get("X-Internal-Health-Token")
    if validate_internal_health_token(internal_health_token):
        return await MonitorService().get_health_status()
    
    if current_user and current_user.role == UserRoleEnum.ADMIN:
        return await MonitorService().get_health_status()
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only admins can use this resource.",
    )
