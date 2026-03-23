from sqlalchemy import Column, Enum, ForeignKey, UniqueConstraint, Boolean, DateTime, func
from sqlalchemy.orm import relationship

from app.infrastructure.db.base import Base
from app.domain.experiments import ExperimentMemberRoleEnum


class ExperimentMember(Base):
    __tablename__ = "experiment_members"

    experiment_id = Column(
        ForeignKey("experiments.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_id = Column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    role = Column(
        Enum(ExperimentMemberRoleEnum, name="experiment_member_role_enum"),
        nullable=False,
        default=ExperimentMemberRoleEnum.EDITOR,
    )
    is_active = Column(Boolean, default=True, nullable=False)

    joined_by_user_id = Column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    joined_at = Column(
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

    experiment = relationship("Experiment", back_populates="members")
    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    joined_by = relationship("User", foreign_keys=[joined_by_user_id])

    __table_args__ = (
        UniqueConstraint(
            "experiment_id",
            "user_id",
            name="uq_experiment_member",
        ),
    )
