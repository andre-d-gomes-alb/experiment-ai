from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.infrastructure.db.base import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String(100), primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(JSONB, nullable=True, default=dict, server_default="{}")

    mlflow_experiment_id = Column(String(50), unique=True, nullable=True, index=True)

    owner_id = Column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
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
    archived_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    owner = relationship("User", lazy="joined")
    members = relationship(
        "ExperimentMember",
        cascade="all, delete-orphan",
        back_populates="experiment",
    )
    variables = relationship(
        "ExperimentVariable",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    connections = relationship(
        "ExperimentConnection",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    pipelines = relationship(
        "ExperimentPipeline",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
