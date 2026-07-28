from fastapi import APIRouter, Path, Depends
from typing import List, Optional

from app.infrastructure.db.models import User
from app.core.security import get_current_user
from app.application.experiments import ExperimentConnectionsService
from .schemas import ConnectionCreate, ConnectionUpdate, ConnectionRead, ConnectionDetailRead
from app.api.v1.experiments import get_experiment_connections_service


router = APIRouter()


# Create a new experiment connection
@router.post("/", response_model=ConnectionRead)
async def create_experiment_connection(
    experiment_id: str = Path(...),
    data: ConnectionCreate = None,
    current_user: User = Depends(get_current_user),
    service: ExperimentConnectionsService = Depends(get_experiment_connections_service),
):
    return await service.create(
        experiment_id=experiment_id,
        data=data,
        current_user=current_user,
    )

# List experiment connections
@router.get("/", response_model=List[ConnectionRead])
async def list_experiment_connections(
    experiment_id: str = Path(...),
    description: Optional[str] = None,
    conn_type: Optional[str] = None,
    host: Optional[str] = None,
    schema_name: Optional[str] = None,
    port: Optional[int] = None,
    sort: str = "id asc",
    current_user: User = Depends(get_current_user),
    service: ExperimentConnectionsService = Depends(get_experiment_connections_service),
):
    return await service.list(
        experiment_id=experiment_id,
        current_user=current_user,
        description=description,
        conn_type=conn_type,
        host=host,
        schema_name=schema_name,
        port=port,
        sort=sort,
    )

# Get a experiment connection by ID
@router.get("/{connection_id}", response_model=ConnectionDetailRead)
async def get_experiment_connection(
    experiment_id: str = Path(...),
    connection_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentConnectionsService = Depends(get_experiment_connections_service),
):
    return await service.get(
        experiment_id=experiment_id,
        connection_id=connection_id,
        current_user=current_user,
    )

# Update a experiment connection
@router.patch("/{connection_id}", response_model=ConnectionRead)
async def update_experiment_connection(
    experiment_id: str = Path(...),
    connection_id: str = Path(...),
    data: ConnectionUpdate = None,
    current_user: User = Depends(get_current_user),
    service: ExperimentConnectionsService = Depends(get_experiment_connections_service),
):
    return await service.update(
        experiment_id=experiment_id,
        connection_id=connection_id,
        data=data,
        current_user=current_user,
    )

# Delete a experiment connection
@router.delete("/{connection_id}")
async def delete_experiment_connection(
    experiment_id: str = Path(...),
    connection_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentConnectionsService = Depends(get_experiment_connections_service),
):
    await service.delete(
        experiment_id=experiment_id,
        connection_id=connection_id,
        current_user=current_user,
    )
    return {"detail": "Connection deleted"}

# Test a experiment connection
@router.post("/{connection_id}/test")
async def test_experiment_connection(
    experiment_id: str = Path(...),
    connection_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    service: ExperimentConnectionsService = Depends(get_experiment_connections_service),
):
    return await service.test(
        experiment_id=experiment_id,
        connection_id=connection_id,
        current_user=current_user,
    )
