from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func, Enum
from sqlalchemy.orm import relationship

from app.infrastructure.db.base import Base
from app.domain.experiments import ExperimentPipelineStatusEnum


class ExperimentPipeline(Base):
    __tablename__ = "experiment_pipelines"

    experiment_id = Column(
        ForeignKey("experiments.id", ondelete="CASCADE"),
        primary_key=True,
    )

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(ExperimentPipelineStatusEnum, name="experiment_pipeline_status_enum"),
        nullable=False,
        default=ExperimentPipelineStatusEnum.ACTIVE,
    )

    created_by_user_id = Column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    paused_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    experiment = relationship("Experiment", back_populates="pipelines")
    created_by = relationship("User")
