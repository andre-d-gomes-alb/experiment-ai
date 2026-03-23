from sqlalchemy import Column, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.infrastructure.db.base import Base


class ExperimentVariable(Base):
    __tablename__ = "experiment_variables"

    experiment_id = Column(
        ForeignKey("experiments.id", ondelete="CASCADE"),
        primary_key=True,
    )

    id = Column(String, primary_key=True)
    description = Column(String, nullable=True)

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

    experiment = relationship("Experiment", back_populates="variables")
    created_by = relationship("User")
