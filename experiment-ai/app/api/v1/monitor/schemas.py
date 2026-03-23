from pydantic import BaseModel
from typing import Any, Dict


class MonitorResponse(BaseModel):
    app: str
    airflow: Dict[str, Any]
    mlflow: str
