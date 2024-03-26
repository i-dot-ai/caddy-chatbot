run-tests:
	sam local start-lambda --env-vars env.json 2> /dev/null & #Disable SAM output
	sleep 5 # Wait for the lambda to start
	pytest -vv
	pkill -f "sam local start-lambda"

requirements-dev:
	pip install -r requirements-dev.txt

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
