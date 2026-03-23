from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import LoginRequest, Token, PasswordChangeRequest
from app.api.v1.users import UserProfileRead, UserProfileUpdate, UserRead
from app.infrastructure.db.models import User
from app.infrastructure.db.session import get_db
from app.core.security import get_current_user
from app.application.auth import AuthService


router = APIRouter()


# User login
@router.post("/login", response_model=Token)
async def login(
    form_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    token = await AuthService(db).login(
        form_data.email,
        form_data.password,
    )
    return {"access_token": token, "token_type": "Bearer"}

# Get current user profile
@router.get("/me", response_model=UserProfileRead)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await AuthService(db).get_me(current_user)

# Update user profile
@router.patch("/me", response_model=UserRead)
async def update_profile(
    user_in: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await AuthService(db).update_profile(
        current_user,
        full_name=user_in.full_name,
        company=user_in.company,
    )

# Change user password
@router.post("/change-password")
async def change_password(
    passwords: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await AuthService(db).change_password(
        current_user,
        passwords.old_password,
        passwords.new_password,
    )
    return {"msg": "Password updated successfully"}
