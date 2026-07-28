from pydantic import BaseModel, validator
from typing import Optional, Dict
from datetime import datetime

from app.core.resource_keys import validate_experiment_resource_identifier


class ConnectionCreate(BaseModel):
    id: str
    conn_type: str
    description: Optional[str] = None
    host: Optional[str] = None
    login: Optional[str] = None
    schema_name: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None
    extra: Optional[Dict] = None

    @validator("id")
    def valid_connection_id(cls, v):
        return validate_experiment_resource_identifier(v, field_name="connection id")

class ConnectionUpdate(BaseModel):
    conn_type: Optional[str] = None
    description: Optional[str] = None
    host: Optional[str] = None
    login: Optional[str] = None
    schema_name: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None
    extra: Optional[Dict] = None

class ConnectionCreator(BaseModel):
    user_id: int
    email: str

class ConnectionRead(BaseModel):
    id: str
    conn_type: str
    description: Optional[str]
    host: Optional[str]
    login: Optional[str]
    schema_name: Optional[str]
    port: Optional[int]
    password: Optional[str]
    extra: Optional[Dict]
    created_at: datetime
    updated_at: datetime

class ConnectionDetailRead(ConnectionRead):
    created_by: ConnectionCreator
