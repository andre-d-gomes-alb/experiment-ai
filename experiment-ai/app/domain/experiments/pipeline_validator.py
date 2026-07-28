import ast
import re


PROHIBITED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "multiprocessing",
}

PROHIBITED_CALLS = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "globals",
    "locals",
}

DANGEROUS_ATTRS = {
    "system",
    "popen",
    "spawn",
    "exec",
    "execv",
}

URL_PATTERN = re.compile(
    r"(postgresql|mysql|mongodb|redis|amqp|kafka|http|https):\/\/",
    re.IGNORECASE,
)


class PipelineValidationError(Exception):
    pass


def validate_pipeline_code(
    code: str,
    experiment_prefix: str,
):
    try:
        tree = ast.parse(code)
    except Exception as e:
        raise PipelineValidationError(
            f"Invalid python code: {e}"
        )

    importlib_aliases = set()
    import_module_aliases = set()

    # Detect imports + aliases
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                root_module = n.name.split(".")[0]
                if root_module in PROHIBITED_MODULES:
                    raise PipelineValidationError(
                        f"Import '{n.name}' is prohibited."
                    )
                if n.name == "importlib":
                    importlib_aliases.add(n.asname or n.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module in PROHIBITED_MODULES:
                    raise PipelineValidationError(
                        f"Import from '{node.module}' is prohibited."
                    )
            if node.module == "importlib":
                for n in node.names:
                    if n.name == "import_module":
                        import_module_aliases.add(n.asname or n.name)

        elif isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Name):
                if node.value.id in importlib_aliases:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            importlib_aliases.add(target.id)

    # Main validation
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):

            # builtin dangerous calls
            if isinstance(node.func, ast.Name):
                if node.func.id in PROHIBITED_CALLS:
                    raise PipelineValidationError(
                        f"Call '{node.func.id}' is prohibited."
                    )
                
            # getattr protection
            if isinstance(node.func, ast.Name) and node.func.id == "getattr":
                if len(node.args) >= 2:
                    attr_arg = node.args[1]
                    if isinstance(attr_arg, ast.Constant):
                        attr_name = attr_arg.value
                        if attr_name in DANGEROUS_ATTRS:
                            raise PipelineValidationError(
                                f"Dynamic getattr access to '{attr_name}' is prohibited."
                            )

            # importlib.import_module(...)
            if isinstance(node.func, ast.Attribute):
                if (node.func.attr == "import_module"
                    and getattr(node.func.value, "id", None) in importlib_aliases):
                    if node.args and isinstance(node.args[0], ast.Constant):
                        module_name = node.args[0].value
                        if isinstance(module_name, str):
                            root_module = module_name.split(".")[0]
                            if root_module in PROHIBITED_MODULES:
                                raise PipelineValidationError(
                                    f"Dynamic import of prohibited module '{root_module}'."
                                )

            # import_module(...)
            if isinstance(node.func, ast.Name):
                if node.func.id in import_module_aliases:
                    if node.args and isinstance(node.args[0], ast.Constant):
                        module_name = node.args[0].value
                        if isinstance(module_name, str):
                            root_module = module_name.split(".")[0]
                            if root_module in PROHIBITED_MODULES:
                                raise PipelineValidationError(
                                    f"Dynamic import of prohibited module '{root_module}'."
                                )

            # Check Variables
            if (getattr(node.func, "attr", None) == "get"
                and getattr(node.func.value, "id", None) == "Variable"):
                if node.args and isinstance(node.args[0], ast.Constant):
                    var_name = node.args[0].value
                    if not isinstance(var_name, str):
                        raise PipelineValidationError(
                            "Variable name must be string literal."
                        )
                    if not var_name.startswith(experiment_prefix):
                        raise PipelineValidationError(
                            f"Variable '{var_name}' must start with experiment prefix 'exp__<experiment_id>__'."
                        )

            # Check Connections
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get_connection":
                if node.args and isinstance(node.args[0], ast.Constant):
                    conn_id = node.args[0].value
                    if not isinstance(conn_id, str):
                        raise PipelineValidationError(
                            "Connection id must be string literal."
                        )
                    if not conn_id.startswith(experiment_prefix):
                        raise PipelineValidationError(
                            f"Connection '{conn_id}' must start with experiment prefix 'exp__<experiment_id>__'."
                        )
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg and kw.arg.endswith("_conn_id"):
                        if isinstance(kw.value, ast.Constant):
                            conn_id = kw.value.value

                            if not isinstance(conn_id, str):
                                raise PipelineValidationError(
                                    f"Connection id for '{kw.arg}' must be a string literal."
                                )

                            if not conn_id.startswith(experiment_prefix):
                                raise PipelineValidationError(
                                    f"Connection '{conn_id}' must start with experiment prefix 'exp__<experiment_id>__'."
                                )
                        else:
                            raise PipelineValidationError(
                                f"Connection id for '{kw.arg}' must be a string literal."
                            )

            # MLflow protection
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {"set_tracking_uri", "set_experiment"}:
                    raise PipelineValidationError(
                        f"mlflow.{node.func.attr} is managed by platform and cannot be overridden."
                    )

        # Hardcoded URL detection
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                if URL_PATTERN.search(node.value):
                    raise PipelineValidationError(
                        "Hardcoded URL detected. Use Airflow Connections instead."
                    )


def extract_registered_model_names_pipeline_code(code: str) -> set[str]:
    try:
        tree = ast.parse(code)
    except Exception as e:
        raise PipelineValidationError(f"Invalid python code: {e}")

    model_names = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            is_mlflow_call = False
            
            if isinstance(node.func, ast.Attribute):
                curr = node.func.value
                while isinstance(curr, ast.Attribute):
                    curr = curr.value
                if isinstance(curr, ast.Name) and curr.id == "mlflow":
                    is_mlflow_call = True

            if not is_mlflow_call:
                continue

            func_name = node.func.attr

            for kw in node.keywords:
                if kw.arg == "registered_model_name":
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        model_names.add(kw.value.value)
                    else:
                        raise PipelineValidationError(
                            "The 'registered_model_name' argument must be a string literal, "
                            "not a variable or expression."
                        )

            if func_name == "register_model":
                if len(node.args) >= 2:
                    name_arg = node.args[1]
                    if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
                        model_names.add(name_arg.value)
                    else:
                        raise PipelineValidationError(
                            "The model name in 'mlflow.register_model' must be a string literal, "
                            "not a variable or expression."
                        )
                elif len(node.args) < 2 and not any(kw.arg == "name" for kw in node.keywords):
                    raise PipelineValidationError("mlflow.register_model requires a model name.")

    return model_names
