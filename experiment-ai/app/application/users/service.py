from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.repositories import UserRepository
from app.infrastructure.db.models import User
from app.core.security import hash_password, validate_password
from app.core.enums import UserRoleEnum
from app.api.v1.users import UserCreate, UserUpdate, UserProfileRead, UserExperimentRead


ALLOWED_SORT_FIELDS = {
    "id",
    "email",
    "full_name",
    "company",
    "role",
    "is_active",
    "created_at",
    "updated_at",
}


class UserService:
    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)

    async def create_user(
        self,
        user_in: UserCreate,
    ):
        validate_password(user_in.password)
        
        existing = await self.repo.get_by_email(user_in.email)

        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

            existing.is_active = True
            existing.full_name = user_in.full_name
            existing.company = user_in.company
            existing.role = user_in.role
            existing.hashed_password = hash_password(user_in.password)
            return await self.repo.update(existing)

        user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            company=user_in.company,
            hashed_password=hash_password(user_in.password),
            role=user_in.role,
            is_active=True,
        )
        return await self.repo.create(user)

    async def list_users(
        self,
        email: str | None = None,
        full_name: str | None = None,
        company: str | None = None,
        role: UserRoleEnum | None = None,
        is_active: bool | None = None,
        sort: str = "id asc",
    ):
        try:
            field, order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'"
            )

        if field not in ALLOWED_SORT_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field '{field}'"
            )

        if order not in {"asc", "desc"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sort order must be 'asc' or 'desc'"
            )

        return await self.repo.search(
            email=email,
            full_name=full_name,
            company=company,
            role=role,
            is_active=is_active,
            sort_field=field,
            sort_order=order,
        )

    async def get_user_orm(
        self,
        user_id: int,
    ) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

    async def get_user(
        self,
        user_id: int,
    ) -> UserProfileRead:
        user = await self.repo.get_user_with_experiments(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        experiments = [
            UserExperimentRead(
                id=exp["id"],
                name=exp["name"],
                role=exp["role"]
            )
            for exp in getattr(user, "experiments", [])
        ]

        return UserProfileRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            company=user.company,
            role=user.role,
            created_at=user.created_at,
            updated_at=user.updated_at,
            experiments=experiments,
        )

    async def update_user(
        self,
        user: User,
        user_in: UserUpdate,
        admin: bool = False,
    ):
        if user_in.role is not None and admin:
            user.role = user_in.role
        if user_in.full_name is not None:
            user.full_name = user_in.full_name
        if user_in.company is not None:
            user.company = user_in.company
        return await self.repo.update(user)

    async def deactivate_user(
        self,
        user: User,
    ):
        user.is_active = False
        return await self.repo.update(user)
