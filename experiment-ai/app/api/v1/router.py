from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router
from app.api.v1.monitor.router import router as monitor_router
from app.api.v1.users.router import router as users_router
from app.api.v1.experiments.router import router as experiments_router
from app.api.v1.experiments.members.router import router as members_router
from app.api.v1.experiments.variables.router import router as variables_router
from app.api.v1.experiments.connections.router import router as connections_router
from app.api.v1.experiments.pipelines.router import router as pipelines_router
from app.api.v1.experiments.runs.router import router as runs_router
from app.api.v1.experiments.logged_models.router import router as logged_models_router
from app.api.v1.experiments.registered_models.router import router as registered_models_router
from app.api.v1.models.router import router as models_router


api_router = APIRouter()


api_router.include_router(auth_router, prefix="/auth", tags=["AUTH"])

api_router.include_router(monitor_router, prefix="/monitor", tags=["MONITOR"])

api_router.include_router(users_router, prefix="/users", tags=["USERS"])

api_router.include_router(experiments_router, prefix="/experiments", tags=["EXPERIMENTS"])
api_router.include_router(
    members_router, prefix="/experiments/{experiment_id}/members", tags=["Experiment Members"]
)
api_router.include_router(
    variables_router, prefix="/experiments/{experiment_id}/variables", tags=["Experiment Variables"]
)
api_router.include_router(
    connections_router, prefix="/experiments/{experiment_id}/connections", tags=["Experiment Connections"]
)
api_router.include_router(
    pipelines_router, prefix="/experiments/{experiment_id}/pipelines", tags=["Experiment Pipelines"]
)
api_router.include_router(
    runs_router, prefix="/experiments/{experiment_id}/runs", tags=["Experiment Runs"]
)
api_router.include_router(
    logged_models_router, prefix="/experiments/{experiment_id}/logged-models", tags=["Experiment Logged Models"]
)
api_router.include_router(
    registered_models_router, prefix="/experiments/{experiment_id}/registered-models", tags=["Experiment Registered Models"]
)

api_router.include_router(models_router, prefix="/models", tags=["MODELS HUB"])
