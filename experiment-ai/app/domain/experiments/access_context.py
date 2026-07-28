from dataclasses import dataclass
from typing import Optional

from app.domain.experiments import ExperimentMemberRoleEnum


@dataclass(frozen=True)
class ExperimentAccessContext:
    is_owner: bool
    member_role: Optional[ExperimentMemberRoleEnum]
