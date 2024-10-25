requirements-dev:
	pip install poetry
	poetry install

setup-pre-commit:
	pip install pre-commit
	pre-commit install

setup-env-vars:
	@cp example.env .env
	@echo "DOCKER_BUILDKIT=1" >> .env
	@echo "COMPOSE_DOCKER_CLI_BUILD=1" >> .env

ensure-network:
	docker network inspect caddy >/dev/null 2>&1 || docker network create caddy

setup-dev-container: requirements-dev setup-env-vars setup-pre-commit ensure-network

ensure-dynamodb-dir:
	mkdir -p dynamodb-data
	chmod 777 dynamodb-data

install-spacy-pipeline:
	poetry run spacy download en_core_web_sm --quiet

setup-local-database:
	poetry run python utils/setup_dynamo.py

setup-local-environment: requirements-dev install-spacy-pipeline setup-env-vars setup-pre-commit setup-local-database

run-dev:
	cd caddy_chatbot/src && poetry run uvicorn app:app --host 0.0.0.0 --port 8080 --reload

init-dynamodb: ensure-dynamodb-dir
	@echo "Starting services..."
	@docker-compose -f docker-compose.dev.yml up dynamodb-local -d
	@echo "Waiting for DynamoDB to be ready..."
	@sleep 5
	@echo "Initialising tables..."
	@poetry run python utils/setup_dynamo.py || exit 1
	@echo "Tables initialised successfully!"
	@docker-compose -f docker-compose.dev.yml stop dynamodb-local

run-dev-docker: ensure-network init-dynamodb
	@echo "Starting services with logs..."
	@if [ -z "$$(docker images -q caddy-dev:latest)" ]; then \
		echo "Building image for the first time..."; \
		DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker-compose -f docker-compose.dev.yml build; \
	else \
		echo "Using cached image..."; \
	fi
	DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker-compose -f docker-compose.dev.yml up

clean-dev:
	docker-compose -f docker-compose.dev.yml down -v --remove-orphans
	rm -rf dynamodb-data

# Used for manually syncing local prompt changes into your local dynamodb
sync-prompts:
	@was_running=false; \
	if docker-compose -f docker-compose.dev.yml ps dynamodb-local | grep -q "Up"; then \
		was_running=true; \
		echo "DynamoDB is already running..."; \
	else \
		echo "Starting dynamodb..."; \
		docker-compose -f docker-compose.dev.yml up dynamodb-local -d; \
		echo "Waiting for DynamoDB to be ready..."; \
		sleep 5; \
	fi; \
	echo "Loading prompts..."; \
	poetry run python utils/sync_prompts.py || exit_code=$$?; \
	if [ "$$was_running" = false ]; then \
		echo "Stopping DynamoDB..."; \
		docker-compose -f docker-compose.dev.yml stop dynamodb-local; \
	fi; \
	exit $$exit_code
