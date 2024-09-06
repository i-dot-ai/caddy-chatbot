requirements-dev:
	pip install poetry
	poetry install

setup-pre-commit:
	pre-commit install

setup-cloud-env-vars:
	@cp example.env .env

setup-local-env-vars:
	@cp example.env .env

create-docker-network:
	docker network create caddy

setup-dev-container:
	pip install poetry
	poetry install
	$(MAKE) setup-cloud-env-vars
	$(MAKE) setup-pre-commit
	$(MAKE) create-docker-network

setup-local-environment: requirements-dev setup-local-env-vars setup-pre-commit create-docker-network

run-dev:
	poetry install
	poetry run spacy download en_core_web_sm
	cd caddy_chatbot/src && poetry run uvicorn app:app --host 0.0.0.0 --port 80 --reload
