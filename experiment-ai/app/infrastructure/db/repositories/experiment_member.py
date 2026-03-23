from typing import List, Optional
from sqlalchemy import select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.db.models import ExperimentMember, User
from app.domain.experiments import ExperimentMemberRoleEnum


class ExperimentMemberRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        member: ExperimentMember,
    ) -> ExperimentMember:
        self.session.add(member)
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def search(
        self,
        *,
        experiment_id: str,
        include_inactive: bool,
        email: str | None,
        full_name: str | None,
        company: str | None,
        role: ExperimentMemberRoleEnum | None,
        sort_field: str = "id",
        sort_order: str = "asc",
    ) -> List[ExperimentMember]:
        stmt = (
            select(ExperimentMember)
            .join(ExperimentMember.user)
            .where(ExperimentMember.experiment_id == experiment_id)
            .options(selectinload(ExperimentMember.user))
        )

        if not include_inactive:
            stmt = stmt.where(ExperimentMember.is_active.is_(True))

        if email:
            stmt = stmt.where(User.email.ilike(f"%{email}%"))
        
        if full_name:
            stmt = stmt.where(User.full_name.ilike(f"%{full_name}%"))

        if company:
            stmt = stmt.where(User.company.ilike(f"%{company}%"))

        if role:
            stmt = stmt.where(ExperimentMember.role == role)

        if sort_field == "email":
            column = User.email
        elif sort_field == "full_name":
            column = User.full_name
        elif sort_field == "company":
            column = User.company
        else:
            column = getattr(ExperimentMember, sort_field)

        stmt = stmt.order_by(desc(column) if sort_order == "desc" else asc(column))

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(
        self,
        experiment_id: str,
        user_id: int,
    ) -> Optional[ExperimentMember]:
        result = await self.session.execute(
            select(ExperimentMember)
            .where(
                ExperimentMember.experiment_id == experiment_id,
                ExperimentMember.user_id == user_id,
            )
            .options(selectinload(ExperimentMember.user))
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        member: ExperimentMember,
    ) -> ExperimentMember:
        await self.session.commit()
        await self.session.refresh(member)
        return member
