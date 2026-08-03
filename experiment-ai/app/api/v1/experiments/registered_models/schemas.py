from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime

from app.domain.experiments import ExperimentRegisteredModelVersionAliasEnum


class RegisteredModelVersionRead(BaseModel):
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

class RegisteredModelVersionDetailRead(RegisteredModelVersionRead):
    flavors: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    signature: Optional[Dict[str, Any]] = None
    saved_input_example_info: Optional[Dict[str, Any]] = None

class RegisteredModelAliasesRead(BaseModel):
    alias: str
    version: str | int

class RegisteredModelRead(BaseModel):
    name: str
    description: Optional[str]
    tags: Dict[str, str] = {}
    aliases: List[RegisteredModelAliasesRead] = []
    latest_version: Optional[RegisteredModelVersionRead]
    is_private: bool
    created_at: datetime
    updated_at: datetime

class RegisteredModelDetailRead(BaseModel):
    name: str
    description: Optional[str]
    tags: Dict[str, str] = {}
    aliases: List[RegisteredModelAliasesRead] = []
    latest_version: Optional[RegisteredModelVersionDetailRead]
    is_private: bool
    created_at: datetime
    updated_at: datetime

class RegisteredModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    is_private: Optional[bool] = None

class RegisteredModelVersionUpdate(BaseModel):
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    aliases: Optional[List[ExperimentRegisteredModelVersionAliasEnum]] = None

class RegisteredModelVersionPromote(BaseModel):
    target_name: str
    aliases: Optional[List[ExperimentRegisteredModelVersionAliasEnum]] = None

class RegisteredModelVersionPromoteRead(BaseModel):
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
