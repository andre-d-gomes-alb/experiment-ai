from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class ExternalDependencyError(Exception):
    """
    Raised when an external system fails
    (Airflow, MLflow, etc.)
    """
    pass


def register_error_handlers(app: FastAPI):
    @app.exception_handler(ExternalDependencyError)
    async def external_dependency_handler(request: Request, exc: ExternalDependencyError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "detail": "Failure of an internal dependency. Please contact platform support."
            },
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal server error: {str(exc)}"}
        )
