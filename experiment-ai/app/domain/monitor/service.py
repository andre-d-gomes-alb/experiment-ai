from app.infrastructure.airflow import AirflowMonitor
from app.infrastructure.mlflow import MlflowMonitor


class MonitorDomainService:
    async def get_health_status(self) -> dict:
        airflow = AirflowMonitor()
        mlflow = MlflowMonitor()
        airflow_status = None

        try:
            airflow_status = await airflow.health()
        except Exception:
            airflow_status = {"error": "unreachable"}

        mlflow_status = mlflow.health()

        return {
            "app": "healthy",
            "airflow": airflow_status,
            "mlflow": "healthy" if mlflow_status else "unavailable",
        }
