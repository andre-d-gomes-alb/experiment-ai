# ExperimentAI

ExperimentAI is a professional API service that integrates **Airflow** and **MLflow** to manage experiments, pipelines, runs, and registered models in a unified way.

This project uses:

- FastAPI
- SQLAlchemy
- Alembic
- MLflow (Python client)
- Airflow REST API
- Poetry
- Docker & Docker Compose
- Helm (for Kubernetes deployment)

## System Architecture

ExperimentAI acts as an orchestration layer (Middleware) that abstracts the complexities of Airflow and MLflow:

1. **API Layer (FastAPI):** Handles Auth, RBAC, and input validation.
2. **Metadata Store (PostgreSQL):** Stores users, experiment permissions, and resource metadata.
3. **Orchestration Bridge (Airflow):** Manages DAGs, Variables, and Connections via REST API integration.
4. **ML Lifecycle (MLflow):** Manages Runs, Artifacts (models), and the Global Registry.
5. **Worker Sync:** Ensures that resources created in the API are correctly provisioned and namespaced in the external services.

## Tools & Quick Start

### 🚀 Postman Collection
To make integration and testing easier, a **complete Postman Collection** is included:
- **Environment:** Use the provided environment file and update the `BASE_URL` variable.
- **Pre-configured:** All endpoints include body schemas and authentication headers.
- **Workflow:** Includes a sequence for Login -> Create Experiment -> Model -> Predict.

### 📜 Swagger Documentation
Once the app is running, you can access the interactive documentation at:
- **Swagger UI:** `/docs`

## RBAC Matrix (Role-Based Access Control)

| Module | Consumer | Contributor | Admin |
| :--- | :---: | :---: | :---: |
| Auth / Me | ✅ | ✅ | ✅ |
| System Monitor | ❌ | ❌ | ✅ |
| Users Management | ❌ | ❌ | ✅ |
| Create Experiments | ❌ | ✅ | ✅ |
| Pipelines / MLflow Tracking | ❌ | ✅* | ✅ |
| Models Hub (Read) | ✅ | ✅ | ✅ |
| Models Hub (Predict)| ✅ | ✅ | ✅ |

*\* Within authorized experiment members only.*

---

# API Modules

## Authentication (`/api/v1/auth`)

Endpoints related to authentication and user self-management.

- `POST /login`
  - Authenticate user and return JWT access token
  - Body:
    - `email`
    - `password`
  - Returns:
    - `access_token`
    - `token_type` (Bearer)

- `GET /me`
  - Get current authenticated user profile
  - Returns:
    - User basic information
    - Experiments where the user participates (`id`, `name`, `role`)

- `PATCH /me`
  - Update current user profile
  - Body:
    - `full_name` (optional)
    - `company` (optional)
  - Returns user basic information

- `POST /change-password`
  - Change current user password
  - Body:
    - `old_password`
    - `new_password`

## System Monitoring (`/api/v1/monitor`)

Health and connectivity checks.

> ⚠️ Only **ADMIN** users can access monitoring endpoints.

- `GET /health`
  - Returns overall system health
  - Includes:
    - Application status
    - Airflow connectivity
    - MLflow connectivity

## Users Management (`/api/v1/users`)

Administrative endpoints to manage users.

> ⚠️ All endpoints require **ADMIN** role unless stated otherwise.

- `POST /`
  - Create new user
  - Automatically reactivates user if email exists but user is inactive
  - Body:
    - `email`
    - `password`
    - `role`: `admin`, `contributor`, `consumer`
    - `full_name` (optional)
    - `company` (optional)
  - Returns user basic information

- `GET /`
  - List users with filtering and sorting
  - Filters:
    - `email`
    - `full_name`
    - `company`
    - `role`: `admin`, `contributor`, `consumer`
    - `is_active`: `true`, `false`
  - Sorting:
    - `sort=field asc|desc`
  - Returns a list of user basic information

- `GET /{user_id}`
  - Get user by ID
  - Returns:
    - User information
    - Experiments where the user participates (`id`, `name`, `role`)

- `PATCH /{user_id}`
  - Update user
  - Admins cannot update themselves via this endpoint
  - Returns user basic information

- `DELETE /{user_id}`
  - Soft delete user (sets `is_active=false`)

## Experiments (`/api/v1/experiments`)

Manage experiments, experiment membership, and experiment-scoped resources.  
Each experiment defines a **logical domain** that isolates all resources managed through the API. This isolation is enforced by **namespacing external resources** (e.g. Airflow variables, connections, DAG-related assets) using a deterministic prefix derived from the experiment ID. All experiment-scoped resources follow the pattern `exp__<experiment_id>__<resource_id>`.

> ⚠️ Users with role **CONSUMER** have no access to this module.

### Experiments

- `POST /`
  - Create a new experiment
  - Only available to non-consumer users
  - Creator becomes the experiment **owner**
  - Body:
    - `id`
    - `name`
    - `description` (optional)
    - `tags` (optional)
  - Returns experiment basic information

- `GET /`
  - List experiments accessible to the current user
  - Filters:
    - `name`
    - `description`
    - `tag`
    - `owner_id`
    - `user_role`: `owner`, `editor`, `viewer`
    - `include_archived`: `true`, `false`
  - Sorting:
    - `sort=field asc|desc`
  - Archived experiments are excluded by default
  - Returns a list of experiment basic information

- `GET /{experiment_id}`
  - Get experiment details
  - Returns:
    - Experiment information
    - Owner summary (`id`, `email`)
    - Active experiment members list (`user_id`, `email`, `role`)
    - Experiment variables list (`id`, `description`)
    - Experiment connections list (`id`, `description`)
    - Experiment pipelines list (`id`, `name`, `description`)
    - Experiment runs statistics with last run information
    - Experiemnt last logged model
    - Experiment registered models with last version informstion

- `PATCH /{experiment_id}`
  - Update experiment metadata
  - Editable fields:
    - `name`
    - `description`
    - `tags`
  - Returns experiment basic information

- `DELETE /{experiment_id}`
  - Archive experiment (soft delete `archived_at`)

- `POST /{experiment_id}/reactivate`
  - Reactivate archived experiment

### Experiment Members (`/api/v1/experiments/{experiment_id}/members`)

Manage experiment membership.

> ⚠️ Only experiment owners and authorized editors can manage members.

- `POST /`
  - Add a user to the experiment
  - Restrictions:
    - Cannot add users with role `CONSUMER`
    - Owner cannot be added as a member
    - Reactivates member if previously inactive
  - Body:
    - `email`
    - `role`: `editor`, `viewer` (Default: `editor`)
  - Returns experiment member basic information

- `GET /`
  - List experiment members
  - Filters:
    - `email`
    - `full_name`
    - `company`
    - `role`: `editor`, `viewer`
    - `include_inactive`: `false`, `true`
  - Sorting:
    - `sort=field asc|desc`
  - Returns:
    - Experiment member basic information
    - Joined by user (`user_id`, `email`)

- `GET /{user_id}`
  - Get experiment member details
  - Returns experiment member information

- `PATCH /{user_id}`
  - Update member role (`viewer` / `editor`)

- `DELETE /{user_id}`
  - Deactivate experiment member (soft remove)

### Experiment Variables (`/api/v1/experiments/{experiment_id}/variables`)

Manage experiment-scoped variables.

Variables are reconciled between the API and Airflow, with the API acting as the **source of truth** for metadata (e.g. description).

> ⚠️ Users with role **VIEWER** have read-only access  
> ⚠️ Only experiment owners and editors can create, update or delete variables

- `POST /`
  - Create a new variable for the experiment
  - Automatically creates the corresponding Airflow Variable
  - Body:
    - `id`
    - `value`
    - `description` (optional)
  - Returns experiment variable basic information

- `GET /`
  - List variables belonging to the experiment
  - Reconciles variables between API and Airflow before returning results
  - Filters:
    - `description`
  - Sorting:
    - `sort=field asc|desc`
  - Returns a list of experiment variable basic information

- `GET /{variable_id}`
  - Get details of a single variable
  - Reconciles the variable between API and Airflow
  - Returns:
    - Experiment variable information
    - Created by user (`user_id`, `email`)
  - Returns `404` if the variable does not exist (after reconciliation)

- `PATCH /{variable_id}`
  - Update variable value and/or description
  - Body:
    - `value` (optional)
    - `description` (optional)
  - Returns experiment variable basic information

- `DELETE /{variable_id}`
  - Delete a variable from the experiment
  - Removes the variable from:
    - Airflow
    - API database

### Experiment Connections (`/api/v1/experiments/{experiment_id}/connections`)

Manage experiment-scoped connections.

Connections are reconciled between the API and Airflow, with the API acting as the **source of truth** for metadata (e.g. description).

> ⚠️ Users with role **VIEWER** have read-only access  
> ⚠️ Only experiment owners and editors can create, update or delete connections

- `POST /`
  - Create a new connection for the experiment
  - Automatically creates the corresponding Airflow Connection
  - Body:
    - `id`
    - `conn_type`
    - `description` (optional)
    - `host` (optional)
    - `login` (optional)
    - `schema_name` (optional)
    - `port` (optional)
    - `password` (optional)
    - `extra` (optional)
  - Returns experiment connection basic information

- `GET /`
  - List connections belonging to the experiment
  - Reconciles connections between API and Airflow before returning results
  - Filters:
    - `description`
    - `conn_type`
    - `host`
    - `schema_name`
    - `port`
  - Sorting:
    - `sort=field asc|desc`
  - Returns a list of experiment connection basic information

- `GET /{connection_id}`
  - Get details of a single connection
  - Reconciles the connection between API and Airflow
  - Returns experiment connection information
    - Created by user (`id`, `email`)
  - Returns `404` if the connection does not exist (after reconciliation)

- `PATCH /{connection_id}`
  - Update connection details
  - Body:
    - Any connection field (optional)
  - Returns experiment connection basic information

- `DELETE /{connection_id}`
  - Delete a connection from the experiment
  - Removes the connection from:
    - Airflow
    - API database

- `POST /{connection_id}/test`
  - Test connectivity of the connection
  - Returns result of Airflow connection test

### Experiment Pipelines (`/api/v1/experiments/{experiment_id}/pipelines`)

Manage experiment-scoped pipelines (Airflow DAG's). Pipelines represent executable workflows associated with an experiment.

Pipelines are reconciled between the API and Airflow, with the API acting as the **source of truth**.
DAG code is validated before being deployed to Airflow.

> ⚠️ Users with role **VIEWER** have read-only access  
> ⚠️ Only experiment owners and editors can create, update or delete pipelines and pipeline runs

- `POST /`
  - Create a new pipeline
  - Validates DAG code before deployment
  - Body:
    - `id`
    - `name`
    - `description` (optional)
    - `schedule` (optional)
    - `params` (optional)
    - `code_base64` (optional)
  - Returns experiment pipeline basic information

- `GET /`
  - List pipelines belonging to the experiment
  - Filters:
    - `name`
    - `description`
    - `tag`
    - `status`: `creating`, `updating`, `paused`, `active`, `error`
  - Sorting:
    - `sort=field asc|desc`
  - Returns a list of experiment pipeline basic information

- `GET /{pipeline_id}`
  - Get pipeline detail
  - May include validation warnings
  - Returns experiment pipeline information

- `PUT /{pipeline_id}`
  - ⚠️ Update pipeline definition (Do not update, recreate!)
  - Re-validates DAG code before updating
  - Returns experiment pipeline basic information

- `DELETE /{pipeline_id}`
  - Delete pipeline
  - Removes pipeline from Airflow (DAG) and API database

- `POST /{pipeline_id}/activate`
  - Activate pipeline (unpause)

- `POST /{pipeline_id}/pause`
  - Pause pipeline

- `POST /{pipeline_id}/trigger`
  - Trigger manual execution
  - Body:
    - conf (JSON, pipeline params) (optional)
  - Returns experiment pipeline run basic information

- `GET /{pipeline_id}/runs`
  - List pipeline runs
  - Filters:
    - `max_runs_analysed` (Default: 50)
    - `run_type`: `backfill`, `scheduled`, `manual`, `asset_triggered`
    - `state`: `queued`, `running`, `success`, `failed`
    - `triggered_by`: `cli`, `operator`, `rest_api`, `ui`, `test`, `timetable`, `asset`, `backfill`
  - Sorting:
    - `sort=field asc|desc`
  - Returns a list of experiment pipeline run basic information

- `GET /{pipeline_id}/runs/{run_id}`
  - Get run detail including task instances
  - Returns:
    - Experiment pipeline run information
    - Tasks: List of task information

- `DELETE /{pipeline_id}/runs/{run_id}`
  - Delete run

### Experiment Runs (`/api/v1/experiments/{experiment_id}/runs`)

Manage and track execution runs associated with an experiment. This section provides direct integration with MLflow tracking to monitor training metadata and manage run artifacts.

> ⚠️ Users with role **VIEWER** have read-only access.  
> ⚠️ Only experiment owners and editors can delete runs.

- `GET /`
  - List all runs associated with the experiment.
  - Filters:
    - `run_name`
    - `status`: `running`, `scheduled`, `finished`, `failed`, `killed`
    - `metrics`
    - `has_models`: `true`, `false`
    - `include_deleted`: `true`, `false`
  - Sorting:
    - `sort=start_time asc|desc`
  - Returns a list of experiment runs basic information.

- `GET /{run_id}`
  - Get full details for a specific run.
  - Returns experiment run information.

- `DELETE /{run_id}`
  - Permanently removes the run from MLflow tracking.
  - Returns confirmation of deletion.

- `GET /{run_id}/download-artifacts`
  - Download all artifacts associated with the run (models, plots, logs) into a compressed ZIP file for local analysis.
  - Returns a zip file.

### Experiment Logged Models (`/api/v1/experiments/{experiment_id}/logged-models`)

Access and manage models that have been logged as artifacts during experiment runs. These models are in a "pre-registry" state, allowing for validation before being promoted to the formal Model Registry.

> ⚠️ Users with role **VIEWER** have read-only access.  
> ⚠️ Only experiment owners and editors can update or register models.

- `GET /`
  - List all models found within the artifacts of the experiment's runs.
  - Returns a list of logged models basic information.

- `GET /{model_id}`
  - Get detailed metadata for a specific logged model.
  - Returns a specific logged model information.

- `PATCH /{model_id}`
  - Update metadata or tags associated with the logged model artifact.
  - Body:
    - `status`: `unspecified`, `pending`, `ready`, `failed` (optional)
    - `tags` (optional)
  - Returns a specific logged model basic information.

- `GET /{model_id}/download`
  - Downloads the specific model artifacts as a ZIP file.
  - Returns a zip file.

- `POST /{model_id}/register`
  - Promotes the logged model to the **Global Model Registry (Model Hub)**.
  - Body:
    - `name`: The target name in the Model Hub.
    - `description` (optional)
    - `tags` (optional)
    - `aliases`: `production`, `staging`, `dev`, `champion`, `challenger`, `ab_test`, `canary`, `backup`, `deprecated`, `latest` (optional)
  - Returns the created registered model version basic information.

### Experiment Registered Models (`/api/v1/experiments/{experiment_id}/registered-models`)

Manage models from this experiment that have been promoted to the Model Registry. This section allows for governance, versioning control, and lifecycle management (promotion) of registered assets.

> ⚠️ Users with role **VIEWER** have read-only access.  
> ⚠️ Only experiment owners and editors can update, delete, or promote models.

- `GET /`
  - List all registered models in the registry.
  - Filters:
    - `tags`
    - `aliases`
  - Sorting:
    - `sort=field asc|desc`
  - Returns a list of registered models basic information (with last version basic information).

- `GET /{name}`
  - Get details of a specific registered model.
  - Returns registered models information (with last version information).

- `PATCH /{name}`
  - Update details of a specific registered model.
  - Body:
    - `name`
    - `description`
    - `tags`
  - Returns registered models basic information (with last version information).

- `DELETE /{name}`
  - Permanently removes a specific registered model.
  - Returns confirmation of deletion.

- `GET /{name}/versions`
  - List all versions for a specific registered model.
  - Filters:
    - `run_id`
    - `model_id`
    - `tags`
    - `params`
    - `metrics`
    - `aliases`
    - `is_ready`: `true`, `false`
  - Sorting:
    - `sort=field asc|desc`
  - Returns a list of all versions basic information for a specific registered model.

- `GET /{name}/versions/{version}`
  - Get detailed metadata for a specific registered model version.
  - Returns a version information for a specific registered model and version.

- `PATCH /{name}/versions/{version}`
  - Update detailed metadata for a specific registered model version.
  - Returns a version information for a specific registered model and version.

- `DELETE /{name}/versions/{version}`
  - Permanently removes a specific version from the registry.
  - Returns confirmation of deletion.

- `GET /{name}/versions/{version}/download`
  - Download a specific version from the registry.
  - Returns the registered model version artifacts as a ZIP file.

- `POST /{name}/versions/{version}/promote`
  - Promote a specific version from the registry.
  - Manages the model lifecycle by assigning aliases.
  - Body:
    - `description` (optional)
    - `tags` (optional)
    - `aliases`: `production`, `staging`, `dev`, `champion`, `challenger`, `ab_test`, `canary`, `backup`, `deprecated`, `latest` (optional)
  - Returns the created registered model version basic information.

### ⚠️ Reconciliation & Integration Rules

#### Airflow (Orchestration)
- Experiment resources (variables, connections, pipelines) are **namespaced per experiment** in Airflow.
- On read operations:
  - Resources missing in Airflow are removed from the API.
  - Resources missing in the API are removed from Airflow.
  - If metadata differs, the API metadata is applied to Airflow.
- The API is the **source of truth** for experiment resource metadata.

#### MLflow (Tracking & Registry)
- Each API Experiment is strictly mapped to a unique **MLflow Experiment ID**.
- All MLflow resources (Runs, Logged Models, and Registered Models) are scoped by this mapping:
  - **Isolation:** Users can only access MLflow data that belongs to the experiment they are currently authorized in.
  - **Integrity:** Deleting or archiving an experiment in the API will affect the visibility and management of the associated MLflow metadata.
  - **Automation:** The API handles the underlying MLflow client logic to ensure that every run or model logged is automatically tagged and organized within the correct experiment scope.

## Models Hub (`/api/v1/models`)

Manage the model life cycle, including registration, versioning, and experimental inference. This module integrates directly with **MLflow** to provide a centralized model registry.

> All authenticated users can access the Models Hub.  
> ⚠️ Inference is provided as an **experimental** feature with ephemeral loading.

- `GET /`
  - List all registered models in the registry.
  - Filters:
    - `tags`
    - `aliases`
    - `experiment_name`
    - `only_experiment_models`: `true`, `false`
  - Sorting:
    - `sort=field asc|desc`
  - Returns a list of registered models basic information (with last version basic information).

- `GET /{name}`
  - Get details of a specific registered model.
  - Returns registered models information (with last version information).

- `GET /{name}/versions`
  - List all versions for a specific registered model.
  - Filters:
    - `tags`
    - `params`
    - `metrics`
    - `aliases`
  - Sorting:
    - `sort=field asc|desc`
  - Returns a list of all versions basic information for a specific registered model.

- `GET /{name}/versions/{version}`
  - Get detailed metadata for a specific registered model version.
  - Returns a version information for a specific registered model and version.

- `GET /{name}/versions/{version}/download`
  - Download registered model artifacts as a compressed ZIP file.
  - Returns a zip with model artifacts for a specific registered model and version
    - With a README file containing:
        - Registered model information
        - Version details
        - Python demo for loading and making predictions

- `POST /{name}/versions/{version}/predict`
  - Executes a temporary, on-the-fly inference for testing purposes.
  - **Behavior:** The model is loaded into memory, executed, and immediately cleared (`ephemeral loading`) to optimize system resources and prevent "zombie" memory usage.
  - Body:
    - `dataframe_records`: List of dictionaries representing rows to predict.
  - Returns:
    - `predictions`: List of results.
    - `latency_seconds`: Precise execution duration in seconds (float).
    - `predicted_at`: UTC timestamp of the operation.
  - **Error Handling:** If the input schema does not match the model signature, the API returns a `422 Unprocessable Entity` containing a clean `expected_schema` for easy debugging.

---

# Development & Deployment Guide

## Development

### 1) Local development (without Docker)  with reload
For fast iteration with automatic reload.

```
make upgrade                           # Apply all database migrations
make dev                               # Run FastAPI locally with poetry and reload
```

### 2) Development with Docker Compose  with reload
Run the app and database in containers.

#### Start/Stop services
```
make compose-up                        # Start PostgreSQL and the app (with reload)
make compose-down                      # Stop and remove containers
```

#### Create and apply database migrations
```
make migrate M="<message>"             # Create a new Alembic migration
make upgrade                           # Apply DB migrations
```

## Production

### 1) Build production Docker image
Builds and pushes the Docker image using the Helm chart's configured repository and appVersion.

```
make prod IMAGE_MSG="<message>"        # Build + push image with description label
```

### 2) Deploy using Helm Chart

#### Install release
```
helm install <name> <chart_path> -n <namespace>
```

#### Uninstall release
```
helm uninstall <name> -n <namespace>
```

#### Upgrade or install (recommended)
```
helm upgrade --install <name> <chart_path> -n <namespace>
```

## Notes for New Developers

- Always run migrations (`make migrate` + `make upgrade`) when changing the DB models.
- `make upgrade` applies migrations to the DB used in the current environment (local or compose).
- Docker Compose uses `uvicorn --reload` for live development.
- Production migrations are automatically applied by a Kubernetes Job in the Helm chart.
- `make prod` guarantees the produced Docker image matches the chart’s configured appVersion.
- Prefer `helm upgrade --install` for safe production updates.
- Clean logs. The system uses a custom StreamToLogger to redirect stdout/stderr to the logging system. Be aware that some warnings are silenced at the core level to keep logs readable.

---

# Infrastructure Management
The entire stack (Airflow, MLflow, TimescaleDB, and the ExperimentAI API) is orchestrated via **Helmfile**, which synchronizes all individual **Helm charts**. Additionally, a **Makefile** provides a unified interface to automate management tasks with simple commands.

## One-Command Deployment
To provision the namespace, secrets, and all synchronized Helm releases:

```
make deploy
```

## Automated Testing
To validate if all components are correctly installed and communicating (using **Chart Tests**):

```
make test
```

## Environment Cleanup
To teardown the infrastructure and remove the namespace:

```
make clean
```

#### Managing Persistent Data
By default, make clean preserves the physical data stored in the host (volumes). To perform a full reset (deleting all databases and artifacts):
```
make clean DATA=true
```
⚠️ **Warning:** Using DATA=true is irreversible and will delete all experiments, users, and models.

---

## Versioning Strategy

ExperimentAI follows **semantic versioning**:

- **MAJOR** → API version (breaking changes)
- **MINOR** → new endpoints or compatible features
- **PATCH** → bug fixes or minor compatible changes

---

## License & Copyright

Copyright (c) 2026 **Altice Labs, S.A**. All rights reserved.

The unauthorized copying, modification, or distribution of this software and its documentation via any medium is strictly prohibited. **Proprietary and confidential.**
 