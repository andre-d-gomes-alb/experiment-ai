from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import UserCreate, UserRead, UserUpdate, UserProfileRead
from app.infrastructure.db.models import User
from app.infrastructure.db.session import get_db
from app.core.security import get_current_user
from app.core.enums import UserRoleEnum
from app.application.users import UserService


router = APIRouter()


# Create User
@router.post("/", response_model=UserRead)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )
    
    return await UserService(db).create_user(user_in)

# List Users
@router.get("/", response_model=List[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    email: str | None = None,
    full_name: str | None = None,
    company: str | None = None,
    role: UserRoleEnum | None = None,
    is_active: bool | None = True,
    sort: str = "id asc",
):
    if current_user.role != UserRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view users"
        )

    return await UserService(db).list_users(
        email=email,
        full_name=full_name,
        company=company,
        role=role,
        is_active=is_active,
        sort=sort,
    )

# Get User
@router.get("/{user_id}", response_model=UserProfileRead)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view users"
        )

    service = UserService(db)
    return await service.get_user(user_id)

# Update User
@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )

    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /auth/me to update your own profile"
        )

    service = UserService(db)
    user = await service.get_user_orm(user_id)
    return await service.update_user(user, user_in, admin=True)

# Desactivate User (soft delete)
@router.delete("/{user_id}", response_model=UserRead)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )

    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only another admin can delete your profile"
        )

    service = UserService(db)
    user = await service.get_user_orm(user_id)
    return await service.deactivate_user(user)
