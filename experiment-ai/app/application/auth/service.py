from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.db.repositories import UserRepository
from app.infrastructure.db.models import User, Experiment, ExperimentMember
from app.core.security import verify_password, hash_password, create_access_token, validate_password
from app.api.v1.users import UserExperimentRead


class AuthService:
    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)
        self.session = session

    async def login(
        self,
        email: str,
        password: str
    ) -> str:
        user = await self.repo.get_by_email(email)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        return create_access_token(subject=user.email)

    async def get_me(
        self,
        user: User
    ) -> dict:
        owner_stmt = select(Experiment).where(
            Experiment.owner_id == user.id,
            Experiment.archived_at.is_(None),
        )
        owner_result = await self.session.execute(owner_stmt)

        experiments = [
            UserExperimentRead(
                id=e.id,
                name=e.name,
                role="owner",
            )
            for e in owner_result.scalars().all()
        ]

        member_stmt = (
            select(Experiment, ExperimentMember)
            .join(ExperimentMember, ExperimentMember.experiment_id == Experiment.id)
            .where(
                ExperimentMember.user_id == user.id,
                ExperimentMember.is_active.is_(True),
                Experiment.archived_at.is_(None),
            )
        )

        member_result = await self.session.execute(member_stmt)

        for experiment, member in member_result.all():
            experiments.append(
                UserExperimentRead(
                    id=experiment.id,
                    name=experiment.name,
                    role=member.role.value.lower(),
                )
            )

        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "company": user.company,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "experiments": experiments,
        }
    
    async def update_profile(
        self,
        user: User,
        *,
        full_name: str | None = None,
        company: str | None = None
    ) -> dict:
        if full_name is not None:
            user.full_name = full_name
        if company is not None:
            user.company = company

        return await self.repo.update(user)

    async def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str
    ) -> None:
        if not verify_password(old_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid current password"
            )

        validate_password(new_password)
        user.hashed_password = hash_password(new_password)
        await self.repo.update(user)
