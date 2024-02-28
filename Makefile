.PHONY: test-lambda-func

MSG ?= hello world

hanna-build-lambda:
	DOCKER_HOST=unix:///Users/hanna.harding/.docker/run/docker.sock sam build -t template.yaml --use-container

hanna-test-chat-lambda:
	DOCKER_HOST=unix:///Users/hanna.harding/.docker/run/docker.sock sam local invoke ConversationsFunction --event events/gChatMessageEvent.json --env-vars env.json

hanna-test-supervision-lambda:
	DOCKER_HOST=unix:///Users/hanna.harding/.docker/run/docker.sock sam local invoke SuperviseFunction --event events/supervision.json --env-vars env.json

hanna-test-card-clicked-lambda:
	DOCKER_HOST=unix:///Users/hanna.harding/.docker/run/docker.sock sam local invoke SuperviseFunction --event events/cardClicked.json --env-vars env.json

test-lambda-func:
	@source define_env_vars.sh && python conversations/chat.py lambda_handler '{"message_string": "$(MSG)"}'

requirements-dev:
	pip install -r requirements-dev.txt

build-lambda:
	sam build -t template.yaml --use-container

test-chat-lambda:
	sam local invoke ConversationsFunction --event events/gChatMessageEvent.json --env-vars env.json

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
	@sed -i 's/"some_index"/"$(KENDRA_INDEX_ID)"/' env.json

setup-local-env-vars:
	@cp env.json.example env.json

create-docker-network:
	docker network create caddy

setup-dev-container: requirements-dev setup-cloud-env-vars setup-pre-commit create-docker-network

setup-local-environment: requirements-dev setup-local-env-vars setup-pre-commit create-docker-network

deploy:
	sam build -t template.yaml --use-container && sam deploy --guided --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM --resolve-image-repos
