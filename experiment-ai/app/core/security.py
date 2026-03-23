from datetime import datetime, timedelta
from typing import Optional, Any
import re
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.infrastructure.db.repositories import UserRepository
from app.infrastructure.db.models import User
from app.core.config import settings


# Security scheme
api_key_scheme = APIKeyHeader(
    name="Authorization",
    auto_error=False,
)


# Validate password complexity

def validate_password(password: str) -> None:
    """
    Validate password complexity based on the following rules:
    - minimum 8 characters
    - at least 1 uppercase letter
    - at least 1 lowercase letter
    - at least 1 number
    - at least 1 special character
    """
    requirements = {
        "min_8_characters": len(password) >= 8,
        "has_lowercase": bool(re.search(r"[a-z]", password)),
        "has_uppercase": bool(re.search(r"[A-Z]", password)),
        "has_number": bool(re.search(r"\d", password)),
        "has_special_char": bool(re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\\[\];'/]", password))
    }

    if not all(requirements.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Password does not meet security requirements",
                "requirements": requirements
            }
        )


# Password hashing

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# JWT Token management

def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.utcnow() + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": subject,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# Auth dependencies

def get_token_from_header(
    authorization: str | None = Security(api_key_scheme),
) -> str:
    """
    Expect:
    Authorization: Bearer <token>
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    return authorization.replace("Bearer ", "", 1)

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token_from_header),
) -> User:
    payload = decode_access_token(token)

    email: str | None = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await UserRepository(db).get_by_email(email)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


# Internal health token validation for helm chart test

async def get_authenticated_user(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Security(api_key_scheme),
) -> User | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "", 1)

    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None

    email: str | None = payload.get("sub")
    if not email:
        return None

    user = await UserRepository(db).get_by_email(email)

    if not user or not user.is_active:
        return None

    return user

def validate_internal_health_token(token: str | None) -> bool:
    return (
        token is not None
        and token.startswith("health_")
        and token == settings.INTERNAL_HEALTH_TOKEN
    )
