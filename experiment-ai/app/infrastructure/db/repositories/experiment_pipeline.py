from typing import List, Optional
from sqlalchemy import select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.infrastructure.db.models import ExperimentPipeline
from app.domain.experiments import ExperimentPipelineStatusEnum


class ExperimentPipelineRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        pipeline: ExperimentPipeline,
    ) -> ExperimentPipeline:
        self.session.add(pipeline)
        await self.session.commit()
        await self.session.refresh(pipeline)
        return pipeline

    async def list(
        self,
        *,
        experiment_id: str,
        name: str | None = None,
        description: str | None = None,
        p_status: ExperimentPipelineStatusEnum | None = None,
        sort_field: str = "id",
        sort_order: str = "asc",
    ) -> List[ExperimentPipeline]:
        stmt = (
            select(ExperimentPipeline)
            .where(ExperimentPipeline.experiment_id == experiment_id)
            .options(selectinload(ExperimentPipeline.created_by))
        )

        if name:
            stmt = stmt.where(ExperimentPipeline.name.ilike(f"%{name}%"))

        if description:
            stmt = stmt.where(ExperimentPipeline.description.ilike(f"%{description}%"))
        
        if p_status:
            stmt = stmt.where(ExperimentPipeline.status == p_status)

        column = getattr(ExperimentPipeline, sort_field, ExperimentPipeline.id)
        stmt = stmt.order_by(desc(column) if sort_order == "desc" else asc(column))

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(
        self,
        experiment_id: str,
        id: str,
    ) -> Optional[ExperimentPipeline]:
        result = await self.session.execute(
            select(ExperimentPipeline)
            .where(
                ExperimentPipeline.experiment_id == experiment_id,
                ExperimentPipeline.id == id,
            )
            .options(selectinload(ExperimentPipeline.created_by))
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        pipeline: ExperimentPipeline,
    ) -> ExperimentPipeline:
        await self.session.commit()
        await self.session.refresh(pipeline)
        return pipeline

    async def delete(
        self,
        experiment_id: str,
        id: str,
    ):
        pipeline = await self.get(experiment_id, id)
        if pipeline:
            await self.session.delete(pipeline)
            await self.session.commit()

    async def pause(
        self,
        pipeline: ExperimentPipeline,
    ) -> ExperimentPipeline:
        pipeline.status = ExperimentPipelineStatusEnum.PAUSED
        pipeline.paused_at = datetime.utcnow()
        return await self.update(pipeline)

    async def activate(
        self,
        pipeline: ExperimentPipeline,
    ) -> ExperimentPipeline:
        pipeline.status = ExperimentPipelineStatusEnum.ACTIVE
        pipeline.paused_at = None
        return await self.update(pipeline)
