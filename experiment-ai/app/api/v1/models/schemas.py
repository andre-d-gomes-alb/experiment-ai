from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime


class ModelVersionInferenceRequest(BaseModel):
    dataframe_records: List[Dict[str, Any]]

class ModelVersionInferenceResponse(BaseModel):
    predictions: List[Any]
    latency_seconds: float
    predicted_at: datetime

class ModelVersionRead(BaseModel):
    version: str | int
    description: Optional[str]
    tags: Dict[str, str] = {}
    params: Dict[str, str] = {}
    metrics: Dict[str, float] = {}
    aliases: List[str] = []
    created_at: datetime
    updated_at: datetime

class ModelVersionDetailRead(ModelVersionRead):
    flavors: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    signature: Optional[Dict[str, Any]] = None
    saved_input_example_info: Optional[Dict[str, Any]] = None

class ModelAliasesRead(BaseModel):
    alias: str
    version: str | int

class ModelRead(BaseModel):
    name: str
    description: Optional[str]
    tags: Dict[str, str] = {}
    aliases: List[ModelAliasesRead] = []
    latest_version: Optional[ModelVersionRead]
    experiment_name: str | None = None
    is_private: bool
    created_at: datetime
    updated_at: datetime

class ModelDetailRead(BaseModel):
    name: str
    description: Optional[str]
    tags: Dict[str, str] = {}
    aliases: List[ModelAliasesRead] = []
    latest_version: Optional[ModelVersionDetailRead]
    experiment_name: str | None = None
    is_private: bool
    created_at: datetime
    updated_at: datetime
