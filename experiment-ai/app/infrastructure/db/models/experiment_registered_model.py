from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.infrastructure.db.base import Base


class ExperimentRegisteredModel(Base):
    __tablename__ = "experiment_registered_model"

    id = Column(Integer, primary_key=True, autoincrement=True)

    model_name = Column(String, nullable=False)

    experiment_id = Column(
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_by_user_id = Column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    changed_by_user_id = Column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    privated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    public_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    experiment = relationship("Experiment")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    changed_by = relationship("User", foreign_keys=[changed_by_user_id])
