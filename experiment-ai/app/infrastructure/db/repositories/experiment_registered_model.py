from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import ExperimentRegisteredModel


class ExperimentRegisteredModelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_privacy(self, model_name: str) -> bool:
        stmt = (
            select(ExperimentRegisteredModel)
            .where(ExperimentRegisteredModel.model_name == model_name)
            .order_by(desc(ExperimentRegisteredModel.privated_at))
        )

        result = await self.session.execute(stmt)
        last = result.scalars().first()

        if not last:
            return False

        return last.public_at is None

    async def set_privacy(
        self,
        *,
        model_name: str,
        experiment_id: int,
        user_id: int,
        is_private: bool,
    ) -> None:
        stmt = (
            select(ExperimentRegisteredModel)
            .where(ExperimentRegisteredModel.model_name == model_name)
            .order_by(desc(ExperimentRegisteredModel.privated_at))
        )
        result = await self.session.execute(stmt)
        last = result.scalars().first()

        now = datetime.utcnow()

        if not last:
            if not is_private:
                return
        
            entry = ExperimentRegisteredModel(
                model_name=model_name,
                experiment_id=experiment_id,
                created_by_user_id=user_id,
                changed_by_user_id=None,
                privated_at=now,
                public_at=None,
            )
            self.session.add(entry)
            await self.session.commit()
            await self.session.refresh(entry)
            return

        current_is_private = last.public_at is None

        if current_is_private == is_private:
            return

        if current_is_private and not is_private:
            last.changed_by_user_id = user_id
            last.public_at = now
            await self.session.commit()
            await self.session.refresh(last)
            return

        if not current_is_private and is_private:
            entry = ExperimentRegisteredModel(
                model_name=model_name,
                experiment_id=experiment_id,
                created_by_user_id=user_id,
                changed_by_user_id=None,
                privated_at=now,
                public_at=None,
            )
            self.session.add(entry)
            await self.session.commit()
            await self.session.refresh(entry)
            return
