from typing import List, Optional
from sqlalchemy import select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.db.models import ExperimentConnection


class ExperimentConnectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        conn: ExperimentConnection,
    ) -> ExperimentConnection:
        self.session.add(conn)
        await self.session.commit()
        await self.session.refresh(conn)
        return conn

    async def list(
        self,
        *,
        experiment_id: str,
        description: str | None = None,
        sort_field: str = "id",
        sort_order: str = "asc",
    ) -> List[ExperimentConnection]:
        stmt = (
            select(ExperimentConnection)
            .where(ExperimentConnection.experiment_id == experiment_id)
            .options(selectinload(ExperimentConnection.created_by))
        )

        if description:
            stmt = stmt.where(
                ExperimentConnection.description.ilike(f"%{description}%")
            )

        column = getattr(ExperimentConnection, sort_field)
        stmt = stmt.order_by(desc(column) if sort_order == "desc" else asc(column))

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(
        self,
        experiment_id: str,
        id: str
    ) -> Optional[ExperimentConnection]:
        result = await self.session.execute(
            select(ExperimentConnection)
            .where(
                ExperimentConnection.experiment_id == experiment_id,
                ExperimentConnection.id == id,
            )
            .options(selectinload(ExperimentConnection.created_by))
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        conn: ExperimentConnection,
    ) -> ExperimentConnection:
        await self.session.commit()
        await self.session.refresh(conn)
        return conn

    async def delete(
        self,
        experiment_id: str,
        id: str,
    ):
        conn = await self.get(experiment_id, id)
        if conn:
            await self.session.delete(conn)
            await self.session.commit()
