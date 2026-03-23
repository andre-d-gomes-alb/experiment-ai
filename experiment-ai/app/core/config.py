from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_V1_PREFIX: str = "/api/v1"
    APP_VERSION: str = "dev"
    LOG_FILE_ENABLED: bool = False
    IMAGE_TAG: str = "local"
    REGISTRY: str = ""

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    INTERNAL_HEALTH_TOKEN: str
    
    # Database settings
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )

    # Airflow settings
    AIRFLOW_API_BASE_URL: str
    AIRFLOW_USERNAME: str
    AIRFLOW_PASSWORD: str
    AIRFLOW_DAGS_FOLDER: str

    # MLflow settings
    MLFLOW_TRACKING_URI: str
    MLFLOW_TRACKING_USERNAME: str
    MLFLOW_TRACKING_PASSWORD: str
    MLFLOW_S3_ENDPOINT_URL: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
