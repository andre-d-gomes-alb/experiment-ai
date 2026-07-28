from fastapi import HTTPException, status
from typing import List, Optional
import json

from app.infrastructure.db.models import User, ExperimentConnection
from app.infrastructure.db.repositories import ExperimentRepository, ExperimentConnectionRepository
from app.infrastructure.airflow.connections import AirflowConnections
from app.domain.experiments import can_view_experiment, can_edit_experiment
from app.api.v1.experiments.connections import (
    ConnectionCreate, ConnectionUpdate, ConnectionRead, ConnectionDetailRead, ConnectionCreator,
)
from .reconcile import reconcile_experiment_connections, reconcile_experiment_connection
from app.core.resource_keys import experiment_resource_prefix, experiment_resource_key


ALLOWED_SORT_FIELDS = {
    "id",
    "description",
    "conn_type",
    "host",
    "schema_name",
    "port",
    "created_at",
    "updated_at",
}


class ExperimentConnectionsService:
    def __init__(
        self,
        experiment_repo: ExperimentRepository,
        connection_repo: ExperimentConnectionRepository,
        airflow: AirflowConnections,
    ):
        self.experiment_repo = experiment_repo
        self.connection_repo = connection_repo
        self.airflow = airflow

    async def create(
        self,
        *,
        experiment_id: str,
        data: ConnectionCreate,
        current_user: User,
    ) -> ConnectionRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment connections"
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        # Reconcile connections
        conns_db = await reconcile_experiment_connections(
            experiment_id=experiment_id,
            airflow=self.airflow,
            connection_repo=self.connection_repo,
        )
        if any(c.id == data.id for c in conns_db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connection already exists"
            )

        af_connection_id = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=data.id,
        )

        af = await self.airflow.create(
            connection_id=af_connection_id,
            conn_type=data.conn_type.lower() if data.conn_type else None,
            description=data.description,
            host=data.host,
            login=data.login,
            schema=data.schema_name,
            port=data.port,
            password=data.password,
            extra=data.extra,
        )

        conn = ExperimentConnection(
            experiment_id=experiment_id,
            id=data.id,
            description=data.description,
            created_by_user_id=current_user.id,
        )
        await self.connection_repo.create(conn)

        return self._to_read(conn, af)

    async def list(
        self,
        *,
        experiment_id: str,
        current_user: User,
        description: Optional[str] = None,
        conn_type: Optional[str] = None,
        host: Optional[str] = None,
        schema_name: Optional[str] = None,
        port: Optional[int] = None,
        sort: str = "id asc",
    ) -> List[ConnectionRead]:
        _, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment connections"
            )

        try:
            sort_field, sort_order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'"
            )
        
        if sort_field not in ALLOWED_SORT_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field '{sort_field}'",
            )

        if sort_order not in {"asc", "desc"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sort order must be 'asc' or 'desc'"
            )

        # Reconcile connections
        await reconcile_experiment_connections(
            experiment_id=experiment_id,
            airflow=self.airflow,
            connection_repo=self.connection_repo,
        )

        DB_FIELDS = {"id", "description", "created_at", "updated_at"}
        repo_sort_field = sort_field if sort_field in DB_FIELDS else "id"
        repo_sort_order = sort_order if sort_field in DB_FIELDS else "asc"

        conns_db = await self.connection_repo.list(
            experiment_id=experiment_id,
            description=description,
            sort_field=repo_sort_field,
            sort_order=repo_sort_order,
        )

        prefix = experiment_resource_prefix(experiment_id)
        airflow_conns = await self.airflow.list(
            connection_id_pattern=f"{prefix}%"
        )

        airflow_map = {
            c["connection_id"].replace(prefix, ""): c
            for c in airflow_conns
        }

        merged: list[tuple[ExperimentConnection, dict]] = []

        for db_conn in conns_db:
            af = airflow_map.get(db_conn.id)
            if not af:
                continue

            if conn_type and af.get("conn_type", "").lower() != conn_type.lower():
                continue
            if host and (af.get("host") or "").lower() != host.lower():
                continue
            if schema_name and (af.get("schema") or "").lower() != schema_name.lower():
                continue
            if port and af.get("port") != port:
                continue

            merged.append((db_conn, af))

        if sort_field not in DB_FIELDS:
            reverse = sort_order == "desc"
            merged.sort(
                key=lambda x: (
                    x[1].get("schema") if sort_field == "schema_name"
                    else x[1].get(sort_field)
                ),
                reverse=reverse,
            )

        return [
            self._to_read(db, af)
            for db, af in merged
        ]

    async def get(
        self,
        *,
        experiment_id: str,
        connection_id: str,
        current_user: User,
    ) -> ConnectionDetailRead:
        _, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment connections"
            )

        # Reconcile connection
        conn = await reconcile_experiment_connection(
            experiment_id=experiment_id,
            id=connection_id,
            airflow=self.airflow,
            connection_repo=self.connection_repo
        )

        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )

        af_key = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=connection_id,
        )
        af = await self.airflow.get(af_key)

        return ConnectionDetailRead(
            **self._to_read(conn, af).dict(),
            created_by=ConnectionCreator(
                user_id=conn.created_by.id,
                email=conn.created_by.email,
            ),
        )

    async def update(
        self,
        *,
        experiment_id: str,
        connection_id: str,
        data: ConnectionUpdate,
        current_user: User,
    ) -> ConnectionRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment connections"
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        # Reconcile connection
        conn = await reconcile_experiment_connection(
            experiment_id=experiment_id,
            id=connection_id,
            airflow=self.airflow,
            connection_repo=self.connection_repo,
        )

        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )

        af_key = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=connection_id,
        )
        af_current = await self.airflow.get(af_key)
        
        payload = {}

        if data.conn_type is not None:
            payload["conn_type"] = data.conn_type.lower()
        else:
            payload["conn_type"] = af_current["conn_type"]
        if data.description is not None:
            payload["description"] = data.description
            conn.description = data.description
        if data.host is not None:
            payload["host"] = data.host
        if data.login is not None:
            payload["login"] = data.login
        if data.schema_name is not None:
            payload["schema"] = data.schema_name
        if data.port is not None:
            payload["port"] = data.port
        if data.password is not None:
            payload["password"] = data.password
        if data.extra is not None:
            payload["extra"] = data.extra

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        af = await self.airflow.update(
            connection_id=af_key,
            **payload,
        )

        await self.connection_repo.update(conn)

        return self._to_read(conn, af)

    async def delete(
        self,
        *,
        experiment_id: str,
        connection_id: str,
        current_user: User,
    ) -> None:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment connections"
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        # Reconcile connection
        conn = await reconcile_experiment_connection(
            experiment_id=experiment_id,
            id=connection_id,
            airflow=self.airflow,
            connection_repo=self.connection_repo
        )

        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )

        af_key = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=connection_id,
        )
        await self.airflow.delete(af_key)
        await self.connection_repo.delete(experiment_id, connection_id)

    async def test(
        self,
        *,
        experiment_id: str,
        connection_id: str,
        current_user: User,
    ) -> dict:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )
        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to test experiment connections"
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )

        # Reconcile connection
        conn = await reconcile_experiment_connection(
            experiment_id=experiment_id,
            id=connection_id,
            airflow=self.airflow,
            connection_repo=self.connection_repo,
        )

        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )

        af_key = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=connection_id,
        )
        af = await self.airflow.get(af_key)

        return await self.airflow.test(
            connection_id=af_key,
            conn_type=af["conn_type"],
            description=af.get("description"),
            host=af.get("host"),
            login=af.get("login"),
            schema=af.get("schema"),
            port=af.get("port"),
            password=af.get("password"),
            extra=json.loads(af["extra"])
            if isinstance(af.get("extra"), str)
            else af.get("extra"),
        )
    

    # Helpers

    def _to_read(
        self,
        db: ExperimentConnection,
        af: dict
    ) -> ConnectionRead:
        return ConnectionRead(
            id=db.id,
            conn_type=af["conn_type"],
            description=af.get("description"),
            host=af.get("host"),
            login=af.get("login"),
            schema_name=af.get("schema"),
            port=af.get("port"),
            password=af.get("password"),
            extra=json.loads(af["extra"])
            if isinstance(af.get("extra"), str)
            else af.get("extra"),
            created_at=db.created_at,
            updated_at=db.updated_at,
        )
