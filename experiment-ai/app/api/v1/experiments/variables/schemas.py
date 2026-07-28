from pydantic import BaseModel, validator
from typing import Any, Optional
from datetime import datetime

from app.core.resource_keys import validate_experiment_resource_identifier


class VariableCreate(BaseModel):
    id: str
    value: Any
    description: Optional[str] = None

    @validator("id")
    def valid_variable_id(cls, v):
        return validate_experiment_resource_identifier(v, field_name="variable id")

class VariableUpdate(BaseModel):
    value: Any | None = None
    description: Optional[str] = None

class VariableCreator(BaseModel):
    user_id: int
    email: str

class VariableRead(BaseModel):
    id: str
    value: Any
    description: Optional[str]
    is_encrypted: bool
    created_at: datetime
    updated_at: datetime

class VariableDetailRead(VariableRead):
    created_by: VariableCreator
