.PHONY: help dev compose-up compose-down build docker-build docker-push test lint migrate upgrade alembic-revision prod

REGISTRY ?=     # ex: myregistry.io/myorg
IMAGE_NAME = $(if $(REGISTRY),$(REGISTRY)/experiment-ai,experiment-ai)
IMAGE_TAG ?= local
IMAGE_MSG ?= 

help:
	@echo "Makefile targets:"
	@echo "  make dev               -> run locally with poetry uvicorn --reload"
	@echo "  make compose-up        -> docker compose up (dev)"
	@echo "  make compose-down      -> docker compose down"
	@echo "  make build             -> poetry build (optional)"
	@echo "  make docker-build      -> docker build -t $(IMAGE_NAME):$(IMAGE_TAG) ."
	@echo "  make docker-push       -> docker push $(IMAGE_NAME):$(IMAGE_TAG) (requires REGISTRY)"
	@echo "  make test              -> run tests"
	@echo "  make lint              -> run linters"
	@echo "  make migrate M=msg     -> create alembic revision (autogenerate)"
	@echo "  make upgrade           -> alembic upgrade head (DEV ONLY)"

# Dev local with reload
dev:
	poetry install
	poetry run dotenv run -- uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Docker Compose Dev
compose-up:
	docker compose -f docker-compose.dev.yml up --build

compose-down:
	docker compose -f docker-compose.dev.yml down --rmi local

# Python build (optional)
build:
	poetry build

# Build Docker image for production
docker-build:
	docker build --label "description=$(IMAGE_MSG)" -t $(IMAGE_NAME):$(IMAGE_TAG) .

docker-push:
	@echo "Pushing image to registry..."
	docker push $(IMAGE_NAME):$(IMAGE_TAG)

# Tests
test:
	poetry run pytest -q

# Linting
lint:
	poetry run ruff app
	poetry run black --check app

# Alembic - DEV ONLY
migrate:
	poetry run alembic revision --autogenerate -m "$(M)"

upgrade:
	poetry run alembic upgrade head

alembic-revision:
	poetry run alembic revision --autogenerate -m "$(M)"

# Production (with helm chart values)
prod:
	@echo "=> Fetching values from Helm chart..."
	$(eval IMAGE_NAME := $(shell helm show values ./experimentai-chart/ | yq e '.image.repository' -))
	$(eval IMAGE_TAG  := $(shell helm show chart ./experimentai-chart/ | yq e '.appVersion' -))
	@echo "Using image: $(IMAGE_NAME):$(IMAGE_TAG)"
	@echo "=> Building Docker image..."
	$(MAKE) docker-build IMAGE_NAME=$(IMAGE_NAME) IMAGE_TAG=$(IMAGE_TAG) IMAGE_MSG="$(IMAGE_MSG)"
	@echo "=> Pushing Docker image..."
	$(MAKE) docker-push IMAGE_NAME=$(IMAGE_NAME) IMAGE_TAG=$(IMAGE_TAG)
