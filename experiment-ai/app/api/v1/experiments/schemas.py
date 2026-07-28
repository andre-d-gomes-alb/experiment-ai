from typing import List, Dict, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime

from app.core.enums import ExperimentUserRoleEnum
from app.core.resource_keys import validate_experiment_resource_identifier


class OwnerSummary(BaseModel):
    user_id: int
    email: str

class ExperimentMemberSummary(BaseModel):
    user_id: int
    email: str
    role: str

class ExperimentVariableSummary(BaseModel):
    id: str
    description: Optional[str] = None

class ExperimentConnectionSummary(BaseModel):
    id: str
    description: Optional[str] = None

class ExperimentPipelineSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class ExperimentLastRunSummary(BaseModel):
    id: str
    run_name: str
    status: str
    start_time: datetime

class ExperimentRunSummary(BaseModel):
    total_runs: int = 0
    running: int = 0
    scheduled: int = 0
    finished: int = 0
    failed: int = 0
    killed: int = 0
    last_run: Optional[ExperimentLastRunSummary] = None

class ExperimentLoggedModelSummary(BaseModel):
    id: str
    run_id: str
    registered_count: int
    created_at: datetime

class ExperimentRegisteredModelSummary(BaseModel):
    name: str
    description: Optional[str] = None
    latest_version: str
    updated_at: datetime

class ExperimentCreate(BaseModel):
    id: str = Field(..., description="Unique experiment code")
    name: str
    description: Optional[str] = None
    tags: Dict[str, str] = {} 

    @validator("id")
    def valid_experiment_id(cls, v):
        return validate_experiment_resource_identifier(v, field_name="experiment id")

class ExperimentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = None

class ExperimentListRead(BaseModel):
    id: str
    name: str
    description: Optional[str]
    tags: Dict[str, str]
    owner_id: int
    user_role: ExperimentUserRoleEnum
    archived_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ExperimentRead(BaseModel):
    id: str
    name: str
    description: Optional[str]
    tags: Dict[str, str]
    owner: OwnerSummary
    archived_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    members: List[ExperimentMemberSummary] = []
    variables: List[ExperimentVariableSummary] = []
    connections: List[ExperimentConnectionSummary] = []
    pipelines: List[ExperimentPipelineSummary] = []
    runs: ExperimentRunSummary
    last_logged_model: Optional[ExperimentLoggedModelSummary] = None
    registered_models: List[ExperimentRegisteredModelSummary] = []
