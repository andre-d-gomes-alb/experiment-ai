from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html

from app.core.logging import logger
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.middlewares import register_middlewares


def create_app() -> FastAPI:
    app = FastAPI(
        title="ExperimentAI",
        version=settings.APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi="/openapi.json",
    )

    # Custom Swagger UI to disable schemas section
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title,
            # Disable schemas section
            swagger_ui_parameters={"defaultModelsExpandDepth": -1},
        )

    # Middlewares
    register_middlewares(app)

    # Error handlers
    register_error_handlers(app)

    # Routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app

app = create_app()
