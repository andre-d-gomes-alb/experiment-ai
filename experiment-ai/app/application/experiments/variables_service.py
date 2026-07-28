from fastapi import HTTPException, status

from app.domain.experiments import can_view_experiment, can_edit_experiment
from app.infrastructure.db.models import User, ExperimentVariable
from app.infrastructure.db.repositories import ExperimentRepository, ExperimentVariableRepository
from app.infrastructure.airflow.variables import AirflowVariables
from app.api.v1.experiments.variables import (
    VariableCreate, VariableUpdate, VariableRead, VariableDetailRead, VariableCreator,
)
from app.core.resource_keys import experiment_resource_key, experiment_resource_prefix
from .reconcile import reconcile_experiment_variables, reconcile_experiment_variable


ALLOWED_VARIABLE_SORT_FIELDS = {
    "id",
    "description",
    "created_at",
    "updated_at",
}


class ExperimentVariablesService:
    def __init__(
        self,
        experiment_repo: ExperimentRepository,
        variable_repo: ExperimentVariableRepository,
        airflow: AirflowVariables,
    ):
        self.experiment_repo = experiment_repo
        self.variable_repo = variable_repo
        self.airflow = airflow

    async def create(
        self,
        *,
        experiment_id: str,
        data: VariableCreate,
        current_user: User,
    ) -> VariableRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id,
            current_user.id,
            current_user.role,
        )

        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment variables",
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        # Reconcile variables
        vars_db = await reconcile_experiment_variables(
            experiment_id=experiment_id,
            airflow=self.airflow,
            variable_repo=self.variable_repo,
        )
        if any(v.id == data.id for v in vars_db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Variable already exists",
            )

        af_key = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=data.id,
        )

        result = await self.airflow.create(
            key=af_key,
            value=data.value,
            description=data.description,
        )

        var = ExperimentVariable(
            experiment_id=experiment_id,
            id=data.id,
            description=data.description,
            created_by_user_id=current_user.id,
        )
        await self.variable_repo.create(var)

        return VariableRead(
            id=data.id,
            value=result["value"],
            description=result.get("description"),
            is_encrypted=result["is_encrypted"],
            created_at=var.created_at,
            updated_at=var.updated_at,
        )

    async def list(
        self,
        *,
        experiment_id: str,
        current_user: User,
        description: str | None = None,
        sort: str = "id asc",
    ) -> list[VariableRead]:
        _, access = await self.experiment_repo.get_with_access(
            experiment_id,
            current_user.id,
            current_user.role,
        )

        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment variables",
            )

        try:
            field, order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'",
            )

        if field not in ALLOWED_VARIABLE_SORT_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field '{field}'",
            )

        if order not in {"asc", "desc"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sort order must be 'asc' or 'desc'",
            )

        # Reconcile variables
        await reconcile_experiment_variables(
            experiment_id=experiment_id,
            airflow=self.airflow,
            variable_repo=self.variable_repo,
        )

        vars_db = await self.variable_repo.list(
            experiment_id=experiment_id,
            description=description,
            sort_field=field,
            sort_order=order,
        )

        airflow_vars = await self.airflow.list()

        prefix = experiment_resource_prefix(experiment_id)
        airflow_map = {
            v["key"].replace(prefix, ""): v
            for v in airflow_vars
            if v["key"].startswith(prefix)
        }

        results = []
        for var in vars_db:
            v = airflow_map.get(var.id)
            if not v:
                continue
            results.append(
                VariableRead(
                    id=var.id,
                    value=v["value"],
                    description=v.get("description"),
                    is_encrypted=v["is_encrypted"],
                    created_at=var.created_at,
                    updated_at=var.updated_at,
                )
            )

        return results

    async def get(
        self,
        *,
        experiment_id: str,
        variable_id: str,
        current_user: User,
    ) -> VariableDetailRead:
        _, access = await self.experiment_repo.get_with_access(
            experiment_id,
            current_user.id,
            current_user.role,
        )

        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view experiment variables",
            )

        # Reconcile variable
        var = await reconcile_experiment_variable(
            experiment_id=experiment_id,
            id=variable_id,
            airflow=self.airflow,
            variable_repo=self.variable_repo,
        )

        if not var:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Variable not found",
            )

        af_key = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=variable_id
        )
        v = await self.airflow.get(af_key)

        return VariableDetailRead(
            id=variable_id,
            value=v["value"],
            description=v.get("description"),
            is_encrypted=v["is_encrypted"],
            created_by=VariableCreator(
                user_id=var.created_by.id,
                email=var.created_by.email,
            ),
            created_at=var.created_at,
            updated_at=var.updated_at,
        )

    async def update(
        self,
        *,
        experiment_id: str,
        variable_id: str,
        data: VariableUpdate,
        current_user: User,
    ) -> VariableRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id,
            current_user.id,
            current_user.role,
        )

        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment variables",
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        # Reconcile variable
        var = await reconcile_experiment_variable(
            experiment_id=experiment_id,
            id=variable_id,
            airflow=self.airflow,
            variable_repo=self.variable_repo,
        )

        if not var:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Variable not found",
            )

        af_key = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=variable_id,
        )

        if data.value is None:
            airflow_current = await self.airflow.get(af_key)
            value_to_update = airflow_current["value"]
        else:
            value_to_update = data.value

        airflow_kwargs = {"value": value_to_update}
        if data.description is not None:
            airflow_kwargs["description"] = data.description

        v = await self.airflow.update(
            key=af_key,
            **airflow_kwargs
        )

        if data.description is not None:
            var.description = data.description
        if data.value is not None:
            var.value = data.value
        await self.variable_repo.update(var)

        return VariableRead(
            id=variable_id,
            value=v["value"],
            description=v.get("description"),
            is_encrypted=v["is_encrypted"],
            created_at=var.created_at,
            updated_at=var.updated_at,
        )

    async def delete(
        self,
        *,
        experiment_id: str,
        variable_id: str,
        current_user: User,
    ) -> None:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id,
            current_user.id,
            current_user.role,
        )

        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to manage experiment variables",
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        # Reconcile variable
        var = await reconcile_experiment_variable(
            experiment_id=experiment_id,
            id=variable_id,
            airflow=self.airflow,
            variable_repo=self.variable_repo,
        )
        
        if not var:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Variable not found",
            )

        af_key = experiment_resource_key(
            experiment_id=experiment_id,
            resource_key=variable_id,
        )

        await self.airflow.delete(af_key)
        await self.variable_repo.delete(experiment_id, variable_id)
