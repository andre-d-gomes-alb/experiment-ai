from fastapi import HTTPException, status
from typing import Optional, Tuple
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.db.models import Experiment, ExperimentMember
from app.domain.experiments.access_context import ExperimentAccessContext
from app.core.enums import UserRoleEnum


class ExperimentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        experiment: Experiment,
    ) -> Experiment:
        self.session.add(experiment)
        await self.session.commit()
        await self.session.refresh(experiment)
        return experiment

    async def exists_by_id(
        self,
        experiment_id: str,
    ) -> bool:
        result = await self.session.execute(
            select(Experiment.id).where(Experiment.id == experiment_id)
        )
        return result.scalar_one_or_none() is not None

    async def get_by_id(
        self,
        experiment_id: str,
    ) -> Optional[Experiment]:
        result = await self.session.execute(
            select(Experiment)
            .where(Experiment.id == experiment_id)
            .options(
                selectinload(Experiment.members).selectinload(ExperimentMember.user),
                selectinload(Experiment.owner),
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_mlflow_id(
        self,
        mlflow_experiment_id: int,
    ) -> Optional[Experiment]:
        result = await self.session.execute(
            select(Experiment)
            .where(Experiment.mlflow_experiment_id == str(mlflow_experiment_id))
        )
        return result.scalar_one_or_none()

    async def get_with_access(
        self,
        experiment_id: str,
        user_id: int,
        user_role: UserRoleEnum,
    ) -> Tuple[Experiment, ExperimentAccessContext]:
        if user_role == UserRoleEnum.CONSUMER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Consumers cannot access experiments"
            )

        experiment = await self.get_by_id(experiment_id)
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found"
            )
        is_owner = experiment.owner_id == user_id

        member_role = next(
            (
                m.role
                for m in experiment.members
                if m.user_id == user_id and m.is_active
            ),
            None,
        )

        return experiment, ExperimentAccessContext(
            is_owner=is_owner,
            member_role=member_role,
        )
    
    async def search_for_user(
        self,
        *,
        user_id: int,
        include_archived: bool,
        name: str | None = None,
        description: str | None = None,
        tag: str | None = None,
        owner_id: int | None = None,
        sort_field: str = "id",
        sort_order: str = "asc",
    ):
        stmt = (
            select(Experiment, ExperimentMember.role)
            .outerjoin(
                ExperimentMember,
                (ExperimentMember.experiment_id == Experiment.id)
                & (ExperimentMember.user_id == user_id)
                & (ExperimentMember.is_active.is_(True))
            )
            .where(
                (Experiment.owner_id == user_id)
                | (ExperimentMember.user_id == user_id)
            )
            .distinct()
        )

        if not include_archived:
            stmt = stmt.where(Experiment.archived_at.is_(None))

        if name:
            stmt = stmt.where(Experiment.name.ilike(f"%{name}%"))
        
        if description:
            stmt = stmt.where(Experiment.description.ilike(f"%{description}%"))

        if tag:
            if ":" in tag:
                key, value = tag.split(":", 1)
                stmt = stmt.where(
                    Experiment.tags[key].astext == value
                )
            else:
                stmt = stmt.where(
                    Experiment.tags.has_key(tag)
                )

        if owner_id:
            stmt = stmt.where(Experiment.owner_id == owner_id)

        column = getattr(Experiment, sort_field)
        stmt = stmt.order_by(
            column.desc() if sort_order == "desc" else column.asc()
        )

        result = await self.session.execute(stmt)
        return result.all()

    async def update_metadata(
        self,
        experiment_id: str,
        *,
        name: str | None,
        description: str | None,
        tags: dict | None,
    ) -> None:
        values = {}
        if name is not None:
            values["name"] = name
        if description is not None:
            values["description"] = description
        if tags is not None:
            values["tags"] = tags

        if values:
            await self.session.execute(
                update(Experiment)
                .where(Experiment.id == experiment_id)
                .values(**values)
            )
            await self.session.commit()
            
            obj = await self.session.get(Experiment, experiment_id)
            if obj:
                await self.session.refresh(obj)

    async def archive(
        self,
        experiment_id: str,
        archive: bool = True,
    ) -> None:
        await self.session.execute(
            update(Experiment)
            .where(Experiment.id == experiment_id)
            .values(archived_at=func.now() if archive else None)
        )
        await self.session.commit()
        
        obj = await self.session.get(Experiment, experiment_id)
        if obj:
            await self.session.refresh(obj)

    async def get_by_name(
        self,
        name: str,
    ) -> Optional[Experiment]:
        result = await self.session.execute(
            select(Experiment)
            .where(Experiment.name == name)
            .options(
                selectinload(Experiment.members).selectinload(ExperimentMember.user),
                selectinload(Experiment.owner),
            )
        )
        return result.scalar_one_or_none()
