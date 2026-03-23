from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from typing import Dict
import base64

from app.core.config import settings


class AirflowDagFileWriter:
    def __init__(self):
        self.dags_root = Path(settings.AIRFLOW_DAGS_FOLDER)
        self.env = Environment(
            loader=FileSystemLoader(
                Path(__file__).parent / "dag_templates"
            ),
            autoescape=False,
        )

    def write_pipeline(
        self,
        *,
        pipeline_id: str,
        context: Dict,
    ) -> Path:
        self.dags_root.mkdir(parents=True, exist_ok=True)

        path = self.dags_root / f"{pipeline_id}.py"

        template = self.env.get_template("pipeline_template.jinja")
        content = template.render(**context)

        path.write_text(content, encoding="utf-8")
        return path
    
    def delete_pipeline(
        self,
        *,
        pipeline_id: str,
    ) -> None:
        path = self.dags_root / f"{pipeline_id}.py"
        if path.exists():
            path.unlink()

    def calculate_dag_hash(
        self,
        *,
        pipeline_id: str,
    ) -> str:
        path = self.dags_root / f"{pipeline_id}.py"
        if not path.exists():
            return ""
        
        content = path.read_text(encoding="utf-8")
        return base64.b64encode(content.encode("utf-8")).decode("utf-8")
