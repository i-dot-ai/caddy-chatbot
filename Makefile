run-tests:
	sam build -t template.yaml --use-container
	sam local start-lambda --env-vars env.json 2> /dev/null & #Disable SAM output
	sleep 10 # Wait for the lambda to start
	pytest -vv
	pkill -f "sam local start-lambda"

requirements-dev:
	pip install -r requirements.txt

build-lambda:
	sam build -t template.yaml --use-container

test-conversations-lambda:
	sam local invoke ConversationsFunction --event tests/events/CaddyLocalMessageEvent.json --env-vars env.json

test-pii-detection:
	sam local invoke ConversationsFunction --event tests/events/CaddyLocalMessageEvent_PII.json --env-vars env.json

test-llm-lambda:
	sam local invoke LlmFunction --event events/ProcessChatMessageEvent.json --env-vars env.json

test-supervision-lambda:
	sam local invoke SuperviseFunction --event events/supervision.json --env-vars env.json

test-card-clicked-lambda:
	sam local invoke SuperviseFunction --event events/cardClicked.json --env-vars env.json

setup-pre-commit:
	pre-commit install

setup-cloud-env-vars:
	@cp env.json.example env.json
	@sed -i 's/"securi5key"/"$(ANTHROPIC_API_KEY)"/' env.json

setup-local-env-vars:
	@cp env.json.example env.json

create-docker-network:
	docker network create caddy

setup-dev-container: requirements-dev setup-cloud-env-vars setup-pre-commit create-docker-network

setup-local-environment: requirements-dev setup-local-env-vars setup-pre-commit create-docker-network

deploy-prod:
	sam build -t template.yaml --use-container && sam deploy --guided --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM --config-env prod

deploy-dev:
	sam build -t template.yaml --use-container && sam deploy --guided --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM --config-env develop

setup-dev-venv:
	uv venv

install-dev-requirements:
	uv pip sync requirements.txt

freeze-dev-requirements:
	uv pip freeze > requirements.txt

setup_lambda_requirements:
	uv pip compile --output-file $(dir)/requirements.txt $(dir)/requirements.in

setup_venv_conversations:
	$(MAKE) setup_lambda_requirements dir=caddy/conversations

setup_venv_llm:
	$(MAKE) setup_lambda_requirements dir=caddy/llm

setup_venv_supervise:
	$(MAKE) setup_lambda_requirements dir=caddy/supervise

prepare_deployment_dependencies: freeze-dev-requirements setup_venv_conversations setup_venv_llm setup_venv_supervise
