from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime

from app.domain.experiments import ExperimentLoggedModelStatusEnum
from app.domain.experiments import ExperimentRegisteredModelVersionAliasEnum


class LoggedModelRegisteredInfo(BaseModel):
    name: str
    version: str | int

class LoggedModelRead(BaseModel):
    id: str
    name: str
    run_id: str
    status: ExperimentLoggedModelStatusEnum
    tags: Optional[Dict[str, str]]
    params: Dict[str, str]
    metrics: Dict[str, float]
    created_at: datetime
    updated_at: datetime
    registered_count: int

class LoggedModelDetailRead(LoggedModelRead):
    registered_models: List[LoggedModelRegisteredInfo]
    model_type: Optional[str]

class LoggedModelUpdate(BaseModel):
    status: Optional[ExperimentLoggedModelStatusEnum] = None
    tags: Optional[Dict[str, str]] = None

class LoggedModelRegister(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    aliases: Optional[List[ExperimentRegisteredModelVersionAliasEnum]] = None

class LoggedModelRegisterRead(BaseModel):
    registered_name: str
    version: str | int
    description: Optional[str]
    status: str
    run_id: str | None = None
    model_id: str | None = None
    tags: Dict[str, str] = {}
    params: Dict[str, str] = {}
    metrics: Dict[str, float] = {}
    aliases: List[str] = []
    created_at: datetime
    updated_at: datetime
