from enum import Enum


class ExperimentMemberRoleEnum(str, Enum):
    EDITOR = "editor"
    VIEWER = "viewer"

class ExperimentPipelineStatusEnum(str, Enum):
    CREATING = "creating"
    UPDATING = "updating"
    PAUSED = "paused"
    ACTIVE = "active"
    ERROR = "error"

class ExperimentPipelineRunTypeEnum(str, Enum):
    BACKFILL = "backfill"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    ASSET_TRIGGERED = "asset_triggered"

class ExperimentPipelineRunTriggeredByEnum(str, Enum):
    CLI = "cli"
    OPERATOR = "operator"
    REST_API = "rest_api"
    UI = "ui"
    TEST = "test"
    TIMETABLE = "timetable"
    ASSET = "asset"
    BACKFILL = "backfill"

class ExperimentPipelineRunStateEnum(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class ExperimentRunStatusEnum(str, Enum):
    RUNNING = "running"
    SCHEDULED = "scheduled"
    FINISHED = "finished"
    FAILED = "failed"
    KILLED = "killed"

class ExperimentLoggedModelStatusEnum(str, Enum):
    UNSPECIFIED = "unspecified"
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"

class ExperimentRegisteredModelVersionAliasEnum(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEV = "dev"
    CHAMPION = "champion"
    CHALLENGER = "challenger"
    AB_TEST = "ab_test"
    CANARY = "canary"
    BACKUP = "backup"
    DEPRECATED = "deprecated"
    LATEST = "latest"
