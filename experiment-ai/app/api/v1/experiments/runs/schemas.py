from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime


class RunLoggedModelInfo(BaseModel):
    model_id: str
    step: int

class RunInputModelInfo(BaseModel):
    model_id: str

class RunDatasetInputInfo(BaseModel):
    name: str
    source_type: Optional[str]
    digest: Optional[str]

class RunModelPromptInfo(BaseModel):
    name: str
    version: Optional[str]
    
class RunArtifactRead(BaseModel):
    path: str
    is_dir: bool

class RunRead(BaseModel):
    id: str
    run_name: Optional[str]
    status: str
    lifecycle_stage: str
    start_time: datetime
    duration: Optional[int]
    metrics: Dict[str, float]
    logged_models: List[RunLoggedModelInfo] = []

class RunDetailRead(RunRead):
    params: Dict[str, str]
    tags: Dict[str, str]
    dataset_inputs: List[RunDatasetInputInfo] = []
    model_inputs: List[RunInputModelInfo] = []
    linked_prompts: List[RunModelPromptInfo] = []
    artifacts: List[RunArtifactRead] = []
