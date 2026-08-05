from pydantic import BaseModel, validator
from typing import Optional, Dict, List, Literal, Any
from datetime import datetime

from app.core.resource_keys import validate_experiment_resource_identifier
from app.domain.experiments import ExperimentPipelineStatusEnum


class PipelineSchedule(BaseModel):
    value: Any
    type: Literal[
        "cron",
        "preset",
        "interval_seconds",
        "assets",
       #"timetables"
    ]

class PipelineParams(BaseModel):
    value: Any
    type: Literal[
        "string",
        "number",
        "integer",
        "boolean",
        "array",
        "object",
    ] = "string"
    description: Optional[str] = None

class PipelineDefaultArgs(BaseModel):
    owner: Optional[str] = None
    retries: Optional[int] = None
    retry_delay_seconds: Optional[int] = None

class PipelineCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    schedule: Optional[PipelineSchedule] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    catchup: Optional[bool] = None
    default_args: Optional[PipelineDefaultArgs] = None
    max_active_runs: Optional[int] = None
    dagrun_timeout_seconds: Optional[int] = None
    tags: Optional[List[str]] = None
    params: Optional[Dict[str, PipelineParams]] = None
    code_base64: str

    @validator("id")
    def valid_pipeline_id(cls, v):
        return validate_experiment_resource_identifier(v, field_name="pipeline id")

class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    schedule: Optional[PipelineSchedule] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    catchup: Optional[bool] = None
    default_args: Optional[PipelineDefaultArgs] = None
    max_active_runs: Optional[int] = None
    dagrun_timeout_seconds: Optional[int] = None
    tags: Optional[List[str]] = None
    params: Optional[Dict[str, PipelineParams]] = None
    code_base64: str

class PipelineReadBase(BaseModel):
    id: str
    name: str
    description: Optional[str]
    tags: Optional[List[str]]
    status: ExperimentPipelineStatusEnum
    paused_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class PipelineCreator(BaseModel):
    user_id: int
    email: str

class PipelineDetailReadBase(PipelineReadBase):
    created_by: PipelineCreator

class PipelineRead(PipelineReadBase):
    tags: Optional[List[str]]
    schedule: Optional[str]
    schedule_description: Optional[str]
    next_run: Optional[datetime]

class PipelineReadError(PipelineReadBase):
    warnings: List[str]

class PipelineAssets(BaseModel):
    consuming: List[str] = []
    producing: List[str] = []

class PipelineDetailRead(PipelineRead):
    catchup: Optional[bool]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    timezone: Optional[str]
    params: Optional[Dict[str, PipelineParams]]
    max_active_runs: Optional[int]
    version: Optional[int]
    assets: Optional[PipelineAssets]
    dag_hash: Optional[str]
    created_by: PipelineCreator

class PipelineDetailReadError(PipelineReadError):
    created_by: PipelineCreator


# RUNS

class RunRead(BaseModel):
    id: str
    run_type: Optional[str]
    state: Optional[str]
    triggered_by: Optional[str] = None
    execution_date: Optional[datetime]
    duration: Optional[float] = None

class TaskErrorRead(BaseModel):
    type: str
    value: str

class TaskInstanceRead(BaseModel):
    task_name: str
    state: Optional[str]
    duration: Optional[float] = None
    try_number: Optional[int] = None
    error: Optional[TaskErrorRead] = None

class RunDetailRead(RunRead):
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    dag_version: Optional[int] = None
    conf: Optional[Dict] = None
    tasks: List[TaskInstanceRead] = []
