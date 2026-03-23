import re


EXPERIMENT_NAMESPACE_SEPARATOR = "__"

_VALID_IDENTIFIER_REGEX = re.compile(r"^[A-Za-z0-9_]+$")


def experiment_prefix() -> str:
    """
    Experiment name used by mlflow
    """
    return (
        f"exp"
        f"{EXPERIMENT_NAMESPACE_SEPARATOR}"
    )

def experiment_resource_prefix(experiment_id: str) -> str:
    """
    Prefix used to list all resources belonging to a given experiment.
    """
    return (
        f"exp"
        f"{EXPERIMENT_NAMESPACE_SEPARATOR}"
        f"{experiment_id}"
        f"{EXPERIMENT_NAMESPACE_SEPARATOR}"
    )

def experiment_resource_key(
    *,
    experiment_id: str,
    resource_key: str,
) -> str:
    """
    Generates a globally unique key for experiment-scoped resources.
    """
    return (
        f"exp"
        f"{EXPERIMENT_NAMESPACE_SEPARATOR}"
        f"{experiment_id}"
        f"{EXPERIMENT_NAMESPACE_SEPARATOR}"
        f"{resource_key}"
    )

def validate_experiment_resource_identifier(value: str, *, field_name: str) -> str:
    value = value.strip()

    if not _VALID_IDENTIFIER_REGEX.match(value) or EXPERIMENT_NAMESPACE_SEPARATOR in value:
        raise ValueError(
            f"{field_name} must only contain letters, numbers, and underscores"
        )

    return value
