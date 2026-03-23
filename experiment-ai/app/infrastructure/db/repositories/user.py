from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.db.models import User, ExperimentMember, Experiment
from app.core.enums import UserRoleEnum


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user: User,
    ) -> User:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_by_email(
        self,
        email: str,
    ) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        user_id: int,
    ) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        email: str | None = None,
        full_name: str | None = None,
        company: str | None = None,
        role: UserRoleEnum | None = None,
        is_active: bool | None = None,
        sort_field: str = "id",
        sort_order: str = "asc",
    ):
        stmt = select(User)

        if email:
            stmt = stmt.where(User.email.ilike(f"%{email}%"))
        if full_name:
            stmt = stmt.where(User.full_name.ilike(f"%{full_name}%"))
        if company:
            stmt = stmt.where(User.company.ilike(f"%{company}%"))
        if role:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        column = getattr(User, sort_field)
        stmt = stmt.order_by(column.desc() if sort_order == "desc" else column.asc())

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        user: User,
    ) -> User:
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def get_user_with_experiments(
        self,
        user_id: int,
    ) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        experiments = []

        owner_stmt = select(Experiment).where(
            Experiment.owner_id == user_id,
            Experiment.archived_at.is_(None),
        )
        owner_result = await self.session.execute(owner_stmt)

        for exp in owner_result.scalars().all():
            experiments.append(
                {
                    "id": exp.id,
                    "name": exp.name,
                    "role": "owner",
                }
            )

        member_stmt = (
            select(ExperimentMember, Experiment)
            .join(Experiment, ExperimentMember.experiment_id == Experiment.id)
            .where(
                ExperimentMember.user_id == user_id,
                ExperimentMember.is_active.is_(True),
                Experiment.archived_at.is_(None),
            )
        )
        member_result = await self.session.execute(member_stmt)

        for member, experiment in member_result.all():
            experiments.append(
                {
                    "id": experiment.id,
                    "name": experiment.name,
                    "role": member.role.value.lower(),
                }
            )

        user.experiments = experiments
        return user
