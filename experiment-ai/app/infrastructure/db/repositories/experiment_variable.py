from typing import List, Optional
from sqlalchemy import select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.db.models import ExperimentVariable


class ExperimentVariableRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        var: ExperimentVariable,
    ) -> ExperimentVariable:
        self.session.add(var)
        await self.session.commit()
        await self.session.refresh(var)
        return var

    async def list(
        self,
        *,
        experiment_id: str,
        id: str | None = None,
        description: str | None = None,
        sort_field: str = "id",
        sort_order: str = "asc",
    ) -> List[ExperimentVariable]:
        stmt = (
            select(ExperimentVariable)
            .where(ExperimentVariable.experiment_id == experiment_id)
            .options(selectinload(ExperimentVariable.created_by))
        )

        if id:
            stmt = stmt.where(ExperimentVariable.id.ilike(f"%{id}%"))

        if description:
            stmt = stmt.where(
                ExperimentVariable.description.ilike(f"%{description}%")
            )

        column = getattr(ExperimentVariable, sort_field)
        stmt = stmt.order_by(
            desc(column) if sort_order == "desc" else asc(column)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get(
        self,
        experiment_id: str,
        id: str,
    ) -> Optional[ExperimentVariable]:
        result = await self.session.execute(
            select(ExperimentVariable)
            .where(
                ExperimentVariable.experiment_id == experiment_id,
                ExperimentVariable.id == id,
            )
            .options(selectinload(ExperimentVariable.created_by))
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        var: ExperimentVariable,
    ) -> ExperimentVariable:
        await self.session.commit()
        await self.session.refresh(var)
        return var

    async def delete(
        self,
        experiment_id: str,
        id: str,
    ) -> None:
        var = await self.get(experiment_id, id)
        if var:
            await self.session.delete(var)
            await self.session.commit()
