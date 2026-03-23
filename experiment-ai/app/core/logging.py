import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys
import warnings


LOG_FILE_ENABLED = os.environ.get("LOG_FILE_ENABLED", "false").lower() == "true"

LOG_DIR = "/logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

if LOG_FILE_ENABLED:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)

        file_handler = TimedRotatingFileHandler(
            LOG_FILE, when="midnight", interval=1, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    except Exception as e:
        logger.error(f"Could not enable file logging: {e}")

for name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
    uv_logger = logging.getLogger(name)
    uv_logger.handlers.clear()
    uv_logger.propagate = True

# Ignore MLflow sklearn warnings
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.base")

class StreamToLogger:
    def __init__(self, logger, level=logging.INFO):
        self.logger = logger
        self.level = level
        # MLflow
        self.ignore_messages = [
            "already exists. Creating a new version",
            "Copied version",
            "Successfully registered model"
        ]

    def write(self, message):
        message = message.strip()
        if message:
            if any(term in message for term in self.ignore_messages):
                self.logger.log(logging.INFO, "[MLflow] " + message)
            else:
                self.logger.log(self.level, message)

    def flush(self):
        pass

sys.stdout = StreamToLogger(logger, logging.INFO)
sys.stderr = StreamToLogger(logger, logging.ERROR)
