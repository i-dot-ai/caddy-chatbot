requirements-dev:
	pip install poetry
	poetry install

setup-pre-commit:
	pip install pre-commit
	pre-commit install

setup-env-vars:
	@cp example.env .env

create-docker-network:
	docker network create caddy

setup-dev-container:
	pip install poetry
	poetry install
	$(MAKE) setup-env-vars
	$(MAKE) setup-pre-commit
	$(MAKE) create-docker-network

install-spacy-pipeline:
	poetry run spacy download en_core_web_sm --quiet

setup-dynamo:
	poetry run python utils/setup_dynamo.py

setup-postgres:
	-createdb caddy_semantic_router
	source .env && poetry run python utils/load_routes.py

setup-local-environment: requirements-dev install-spacy-pipeline setup-env-vars setup-pre-commit setup-dynamo setup-postgres

setup-docker: create-docker-network

run-dev:
	cd caddy_chatbot/src && poetry run uvicorn app:app --host 0.0.0.0 --port 8080 --reload
