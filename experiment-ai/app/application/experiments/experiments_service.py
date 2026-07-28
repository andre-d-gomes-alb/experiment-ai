from fastapi import HTTPException, status
import json

from app.domain.experiments import (
    can_create_experiment, can_view_experiment, can_edit_experiment, can_archive_experiment,
    ExperimentPipelineStatusEnum,
)
from app.infrastructure.db.models import User, Experiment
from app.infrastructure.db.repositories import (
    ExperimentRepository, ExperimentVariableRepository, 
    ExperimentConnectionRepository, ExperimentPipelineRepository,
)
from app.infrastructure.mlflow import (
    MlflowExperimentService, MlflowExperimentRunService,
    MlflowExperimentLoggedModelService, MlflowExperimentRegisteredModelService,
)
from app.infrastructure.airflow import AirflowVariables, AirflowConnections, AirflowPipelines
from app.api.v1.experiments import (
    ExperimentCreate, ExperimentUpdate, ExperimentRead, ExperimentListRead, OwnerSummary,
    ExperimentMemberSummary, ExperimentVariableSummary, ExperimentConnectionSummary, ExperimentPipelineSummary,
    ExperimentLastRunSummary, ExperimentRunSummary, ExperimentLoggedModelSummary, ExperimentRegisteredModelSummary,
)
from app.core.enums import ExperimentUserRoleEnum
from .reconcile import (
    reconcile_experiment, reconcile_experiments,
    reconcile_experiment_variables, reconcile_experiment_connections, reconcile_experiment_pipelines,
)
from app.core.resource_keys import experiment_prefix
from datetime import datetime


ALLOWED_EXPERIMENT_SORT_FIELDS = {
    "id",
    "name",
    "description",
    "owner_id",
    "created_at",
    "updated_at",
    "archived_at",
}


class ExperimentService:
    def __init__(
            self,
            experiment_repo: ExperimentRepository,
            variable_repo: ExperimentVariableRepository,
            connection_repo: ExperimentConnectionRepository,
            pipeline_repo: ExperimentPipelineRepository,
            mlflow_experiments: MlflowExperimentService,
            mlflow_runs: MlflowExperimentRunService,
            airflow_variables: AirflowVariables,
            airflow_connections: AirflowConnections,
            airflow_pipelines: AirflowPipelines,
            mlflow_logged_models: MlflowExperimentLoggedModelService,
            mlflow_registered_models: MlflowExperimentRegisteredModelService,
        ):
        self.experiment_repo = experiment_repo
        self.variable_repo = variable_repo
        self.connection_repo = connection_repo
        self.pipeline_repo = pipeline_repo
        self.mlflow_experiments = mlflow_experiments
        self.mlflow_runs = mlflow_runs
        self.airflow_variables = airflow_variables
        self.airflow_connections = airflow_connections
        self.airflow_pipelines = airflow_pipelines
        self.mlflow_logged_models = mlflow_logged_models
        self.mlflow_registered_models = mlflow_registered_models

    async def create(
        self,
        *,
        data: ExperimentCreate,
        current_user: User,
    ) -> ExperimentListRead:
        if not can_create_experiment(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User cannot create experiments"
            )
        
        # Reconcile experiments
        exps_db = await reconcile_experiments(
            current_user=current_user,
            mlflow_experiments=self.mlflow_experiments,
            experiment_repo=self.experiment_repo,
        )
        if any(v.id == data.id for v in exps_db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment id already exists"
            )
        if any(v.name == data.name for v in exps_db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment name already exists"
            )
        
        prefix = experiment_prefix()
        tech_name = f"{prefix}{data.id}"

        mlflow_experiment_id = await self.mlflow_experiments.create(
            name=tech_name,
            description=data.description,
            tags=data.tags,
        )

        experiment = Experiment(
            id=data.id,
            name=data.name,
            description=data.description,
            tags=data.tags,
            mlflow_experiment_id=mlflow_experiment_id,
            owner_id=current_user.id,
        )

        await self.experiment_repo.create(experiment)
        
        return ExperimentListRead(
            id=experiment.id,
            name=experiment.name,
            description=experiment.description,
            tags=experiment.tags,
            owner_id=experiment.owner_id,
            user_role=ExperimentUserRoleEnum.OWNER,
            archived_at=experiment.archived_at,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
        )

    async def list(
        self,
        *,
        current_user: User,
        include_archived: bool = False,
        name: str | None = None,
        description: str | None = None,
        tag: str | None = None,
        owner_id: int | None = None,
        user_role: ExperimentUserRoleEnum | None = None,
        sort: str = "id asc",
    ):
        try:
            field, order = sort.split()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort format. Use: 'field asc|desc'"
            )

        if field not in ALLOWED_EXPERIMENT_SORT_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field '{field}'",
            )

        if order not in {"asc", "desc"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sort order must be 'asc' or 'desc'"
            )
        
        # Reconcile experiments
        await reconcile_experiments(
            current_user=current_user,
            mlflow_experiments=self.mlflow_experiments,
            experiment_repo=self.experiment_repo,
        )

        rows = await self.experiment_repo.search_for_user(
            user_id=current_user.id,
            include_archived=include_archived,
            name=name,
            description=description,
            tag=tag,
            owner_id=owner_id,
            sort_field=field,
            sort_order=order,
        )
        id_to_role = {exp.id: member_role for exp, member_role in rows}
        exps_db = [exp for exp, _ in rows]
        
        experiments = []
        for exp in exps_db:
            member_role = id_to_role.get(exp.id)
            if exp.owner_id == current_user.id:
                role = ExperimentUserRoleEnum.OWNER
            else:
                role = ExperimentUserRoleEnum(member_role.value.lower()) if member_role else None

            if user_role and role != user_role:
                continue

            experiments.append(
                ExperimentListRead(
                    id=exp.id,
                    name=exp.name,
                    description=exp.description,
                    tags=exp.tags,
                    owner_id=exp.owner_id,
                    user_role=role,
                    archived_at=exp.archived_at,
                    created_at=exp.created_at,
                    updated_at=exp.updated_at,
                )
            )

        return experiments

    async def get(
        self,
        *,
        experiment_id: str,
        current_user: User,
    ) -> ExperimentRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )

        if not can_view_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User cannot view experiment"
            )
        
        # Reconcile experiment
        experiment = await reconcile_experiment(
            experiment_id=experiment.id,
            experiment_repo=self.experiment_repo,
            mlflow_experiments=self.mlflow_experiments,
        )
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found",
            )

        # Reconcile experiment resources
        variables = await reconcile_experiment_variables(
            experiment_id=experiment.id,
            airflow=self.airflow_variables,
            variable_repo=self.variable_repo,
        )
        connections = await reconcile_experiment_connections(
            experiment_id=experiment.id,
            airflow=self.airflow_connections,
            connection_repo=self.connection_repo,
        )
        pipelines = await reconcile_experiment_pipelines(
            experiment_id=experiment_id,
            airflow=self.airflow_pipelines,
            pipeline_repo=self.pipeline_repo,
        )

        runs = await self.mlflow_runs.list(experiment.mlflow_experiment_id, view_type=1)
        sorted_runs = sorted(
            runs, 
            key=lambda r: r.info.start_time or 0, 
            reverse=True
        )
        runs_stats = {
            "running": 0, "scheduled": 0, "finished": 0, "failed": 0, "killed": 0
        }
        last_run_data = None
        if sorted_runs:
            for r in sorted_runs:
                s = r.info.status.lower()
                if s in runs_stats:
                    runs_stats[s] += 1
            
            last = sorted_runs[0]
            last_run_data = ExperimentLastRunSummary(
                id=last.info.run_id,
                run_name=last.data.tags.get("mlflow.runName", f"Run {last.info.run_id[:8]}"),
                status=last.info.status,
                start_time=datetime.fromtimestamp(last.info.start_time / 1000) if last.info.start_time else None,
            )

        logged_models = await self.mlflow_logged_models.list_logged_models(
            experiment_id=experiment.mlflow_experiment_id,
            status_code=2
        )
        last_logged = None
        if logged_models:
            target = logged_models[0]
            last_logged = ExperimentLoggedModelSummary(
                id=target.model_id,
                run_id=target.source_run_id,
                registered_count=self._logged_model_parse_registered_models(target),
                created_at=datetime.fromtimestamp(target.creation_timestamp / 1000)
            )

        all_reg_models = await self.mlflow_registered_models.list_registered_models()
        registered_summaries = []
        for rm in all_reg_models:
            if await self._registered_model_verify_ownership(rm.name, str(experiment.mlflow_experiment_id)):
                latest = rm.latest_versions[0] if rm.latest_versions else None
                if latest:
                    aliases_str = f" ({', '.join(latest.aliases)})" if latest.aliases else ""
                    registered_summaries.append(
                        ExperimentRegisteredModelSummary(
                            name=rm.name,
                            description=rm.description,
                            latest_version=f"{latest.version}{aliases_str}",
                            updated_at=rm.last_updated_timestamp
                        )
                    )

        return ExperimentRead(
            id=experiment.id,
            name=experiment.name,
            description=experiment.description,
            tags=experiment.tags,
            owner=OwnerSummary(
                user_id=experiment.owner.id,
                email=experiment.owner.email,
            ),
            archived_at=experiment.archived_at,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
            members=[
                ExperimentMemberSummary(
                    user_id=m.user_id,
                    email=m.user.email,
                    role=m.role,
                )
                for m in experiment.members
                if m.is_active
            ],
            variables=[
                ExperimentVariableSummary(
                    id=v.id,
                    description=v.description,
                )
                for v in variables
            ],
            connections=[
                ExperimentConnectionSummary(
                    id=c.id,
                    description=c.description,
                )
                for c in connections
            ],
            pipelines=[
                ExperimentPipelineSummary(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                )
                for p in pipelines
                if p.status==ExperimentPipelineStatusEnum.ACTIVE
            ],
            runs=ExperimentRunSummary(
                **runs_stats,
                total_runs=len(runs),
                last_run=last_run_data,
            ),
            last_logged_model=last_logged,
            registered_models=registered_summaries
        )

    async def update(
        self,
        *,
        experiment_id: str,
        data: ExperimentUpdate,
        current_user: User,
    ) -> ExperimentListRead:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )

        if not can_edit_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User cannot edit experiment"
            )
        
        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is archived and cannot be modified"
            )
        
        # Reconcile experiment
        experiment = await reconcile_experiment(
            experiment_id=experiment.id,
            experiment_repo=self.experiment_repo,
            mlflow_experiments=self.mlflow_experiments,
        )
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found",
            )
        
        mlflow_id = str(experiment.mlflow_experiment_id)
        prefix = experiment_prefix()
        tech_name = f"{prefix}{experiment.id}"
        await self.mlflow_experiments.update(
            experiment_id=mlflow_id,
            name=tech_name,
            description=data.description,
            tags=data.tags,
        )

        await self.experiment_repo.update_metadata(
            experiment_id,
            name=data.name,
            description=data.description,
            tags=data.tags,
        )

        experiment = await self.experiment_repo.get_by_id(experiment_id)
        
        if access.is_owner:
            user_role = "owner"
        else:
            user_role = access.member_role.value.lower()

        return ExperimentListRead(
            id=experiment.id,
            name=experiment.name,
            description=experiment.description,
            tags=experiment.tags,
            owner_id=experiment.owner_id,
            user_role=user_role,
            archived_at=experiment.archived_at,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
        )

    async def archive(
        self,
        *,
        experiment_id: str,
        current_user: User,
    ) -> None:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )

        if not can_archive_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User cannot archive experiment"
            )
        
        # Reconcile experiment
        experiment = await reconcile_experiment(
            experiment_id=experiment.id,
            experiment_repo=self.experiment_repo,
            mlflow_experiments=self.mlflow_experiments,
        )
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found",
            )

        if experiment.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment already archived"
            )
        
        await self.mlflow_experiments.delete(str(experiment.mlflow_experiment_id))

        await self.experiment_repo.archive(experiment_id, archive=True)

    async def reactivate(
        self,
        *,
        experiment_id: str,
        current_user: User,
    ) -> None:
        experiment, access = await self.experiment_repo.get_with_access(
            experiment_id, current_user.id, current_user.role
        )

        if not can_archive_experiment(access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User cannot reactivate experiment"
            )
        
        # Reconcile experiment
        experiment = await reconcile_experiment(
            experiment_id=experiment.id,
            experiment_repo=self.experiment_repo,
            mlflow_experiments=self.mlflow_experiments,
        )
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found",
            )

        if experiment.archived_at is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment already active"
            )
        
        prefix = experiment_prefix()
        tech_name = f"{prefix}{experiment.id}"
        mlflow_id = str(experiment.mlflow_experiment_id) if experiment.mlflow_experiment_id else ""
        new_mlflow_id = await self.mlflow_experiments.ensure_active(
            experiment_id=mlflow_id,
            name=tech_name,
            description=experiment.description,
            tags=experiment.tags
        )

        if new_mlflow_id != mlflow_id:
            experiment.mlflow_experiment_id = new_mlflow_id

        await self.experiment_repo.archive(experiment_id, archive=False)


# Helpers

    def _logged_model_parse_registered_models(self, m) -> int:
        if not m.tags:
            return 0
        
        versions_raw = m.tags.get("mlflow.modelVersions", "[]")
        try:
            data = json.loads(versions_raw)
            if not isinstance(data, list):
                return 0
            
            unique_registrations = {
                f"{v.get('name')}:{v.get('version')}" 
                for v in data 
                if v.get('name') and v.get('version') is not None
            }
            
            return len(unique_registrations)
        except:
            return 0

    async def _registered_model_verify_ownership(
        self,
        name: str,
        mlflow_experiment_id: str,
    ) -> bool:
        versions = await self.mlflow_registered_models.list_registered_model_versions(name)
        if not versions:
            return False
        
        run = None
        for v in versions:
            run = await self.mlflow_runs.get(v.run_id)
            if run:
                break
        
        return str(run.info.experiment_id) == str(mlflow_experiment_id) if run else False
