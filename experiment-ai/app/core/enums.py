from enum import Enum


class UserRoleEnum(str, Enum):
    ADMIN = "admin"
    CONTRIBUTOR = "contributor"
    CONSUMER = "consumer"

class ExperimentUserRoleEnum(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"
