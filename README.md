# Caddy Chatbot

Caddy is an LLM powered co-pilot for customer service functions everywhere. This contains the logic for the chatbot and responses, and also relies on storage of the data using [caddy-scraper](https://github.com/i-dot-ai/caddy-scraper).

## How to Run

This version is intended for deployment on serverless infrastructure, and will ideally use Docker and AWS CLI.

### Environment Management
We recommend using [Poetry](https://github.com/python-poetry/poetry) for managing dependencies.

To create your virtual environment, run

```bash
$ 	poetry install
$ 	poetry shell
```

### AWS CLI

You will require AWS CLI, either [installed directly](https://aws.amazon.com/cli/) or through [pip](https://github.com/aws/aws-cli).

To confirm install, run

```bash
$ aws --version
```

To configure, run

```bash
$ aws configure
```


### Use vscode on github (codespace)

To develop in codespaces, ensure you define your environment variables through Github settings.

[![Open in Remote - Containers](https://img.shields.io/static/v1?label=Remote%20-%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://codespaces.new/i-dot-ai/caddy-chatbot?quickstart=1)

If you are using windows or do not want to install vscode on your machine, you can click on the badge above to spin up a codespace environment.

## Developing with Local DynamoDB

To explore the connection to DynamoDB, I have attached the docker-compose file to spin up a local DynamoDB.  This will have to be span up before using the relevant notebook.

```bash
$ docker compose up
```

## Testing

Running tests on platform agnostic Caddy components with pytest. Tests are stored in tests/caddy_components, and can be invoked by running the below:

```bash
$ docker compose up
```
```bash
$ pytest
```

## Deployment

We'll use AWS CLI and Docker to create and deploy all the relevant resources.

Build and push the container image to your elastic container registry
```bash
$ aws ecr get-login-password | docker login --username AWS --password-stdin "INSERT_ELASTIC_CONTAINER_REGISTRY_ENDPOINT"
```

```bash
$ docker build -f ./caddy_chatbot/Dockerfile -t "INSERT_CONTAINER_REPO_ID":"IMAGE_TAG" .
```

```bash
$ docker tag "INSERT_CONTAINER_REPO_ID":"IMAGE_TAG" "INSERT_ELASTIC_CONTAINER_REGISTRY_ENDPOINT"/"INSERT_CONTAINER_REPO_ID":"IMAGE_TAG"
```

```bash
$ docker push "INSERT_ELASTIC_CONTAINER_REGISTRY_ENDPOINT"/"INSERT_CONTAINER_REPO_ID":"IMAGE_TAG"
```

Once the build is complete, you can deploy the stack with

```bash
$ aws cloudformation deploy --template-file infra/template.yaml --stack-name "INSERT_CUSTOM_STACK_NAME" --capabilities CAPABILITY_NAMED_IAM --parameter-overrides StageName="INSERT_STAGE_NAME"  MessageTableName="INSERT_CADDY_MESSAGE_TABLE_NAME" ResponsesTableName="INSERT_CADDY_RESPONSES_TABLE_NAME" UserTableName="INSERT_CADDY_USERS_TABLE_NAME" OfficesTableName="INSERT_CADDY_OFFICES_TABLE_NAME" EvaluationTableName="INSERT_CADDY_EVALUATION_TABLE_NAME" OpensearchUrl="INSERT_OPENSEARCH_URL*" CaddyServiceAccountSecretArn="INSERT_CADDY_GOOGLE_CHAT_SERVICE_ACCOUNT_SECRET_ARN" CaddySupervisorServiceAccountSecretArn="INSERT_CADDY_SUPERVISOR_GOOGLE_CHAT_SERVICE_ACCOUNT_SECRET_ARN" CaddyImage="INSERT_ELASTIC_CONTAINER_REGISTRY_ENDPOINT"/"INSERT_CONTAINER_REPO_ID":"IMAGE_TAG" CaddySupervisorGoogleCloudProject="INSERT_CADDY_SUPERVISOR_GOOGLE_CHAT_PROJECT_ID" CaddyGoogleCloudProject="INSERT_CADDY_GOOGLE_CHAT_PROJECT_ID" LLM="INSERT_BEDROCK_LLM_MODEL" DomainName="INSERT_DOMAIN_NAME_FOR_SSL_CERT" #pragma: allowlist secret
```
* *OpensearchUrl*: Opensearch is not built into the template yet this must be configured seperately
* *CaddyServiceAccountSecretArn*: Creation of Caddy Google Chat service account in Secret Manager is not built into the template yet and must be created manually
* *CaddySupervisorServiceAccountSecretArn*: Creation of Caddy Supervisor Google Chat service account in Secret Manager is not built into the template yet and must be created manually

For ease of deletion, you can remove all the created resources with

```bash
$ aws cloudformation delete-stack --stack-name "INSERT_CUSTOM_STACK_NAME"
```

# Local Teams Deployment   

```bash
$ docker compose up
```

```bash
$ ngrok http insert-static-url
```

Add app_id, app_password to the example.env from configuration space to generate new tokens. 

In azure bot  - > configuration 
Add static-url into the messaging endpoint
Then in channels use the open in teams button to test locally