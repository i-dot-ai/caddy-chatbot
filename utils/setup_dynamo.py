import caddy_chatbot.src.boot  # noqa: F401

from caddy_core.utils.monitoring import logger
from botocore.exceptions import ClientError
from cfn_tools import load_yaml

from caddy_core.hosting_environment import HostingEnvironment
from caddy_core.utils.tables import dynamodb

from caddy_core.utils import prompts


def get_table_name(table_name) -> str:
    if HostingEnvironment.is_test():
        table_name = f"{table_name}Test"
    return table_name


def sync_prompts(logger, table_name: str = "PromptsTable") -> None:
    table_name = get_table_name(table_name)
    table = dynamodb.Table(table_name)

    prompts_to_sync = {name: getattr(prompts, name) for name in prompts.__all__}

    if logger:
        logger.info(f"Found {len(prompts_to_sync)} prompts to sync")

    for PromptName, Prompt in prompts_to_sync.items():
        if logger:
            logger.debug(f"Attempting to load: {PromptName}")
        try:
            table.put_item(
                Item={
                    "PromptName": f"{PromptName}_PROMPT".upper(),
                    "Prompt": Prompt,
                }
            )

            if logger:
                logger.info(f"Successfully synced prompt: {PromptName}")
        except ClientError as error:
            if logger:
                logger.error(
                    f"Failed to sync prompt {PromptName} with value {Prompt}: {str(error)}"
                )
            raise


def setup_dynamo(logger):
    if not HostingEnvironment.is_dev() and not HostingEnvironment.is_test():
        raise Exception("Refusing to run setup_dynamo in non-dev environment")

    raw_yaml = open("infra/template.yaml").read()
    cloudformation = load_yaml(raw_yaml)

    tables = {
        k: v
        for k, v in cloudformation["Resources"].items()
        if v["Type"] == "AWS::DynamoDB::Table"
    }

    for table_name, t in tables.items():
        # :/ but we'll make it better!
        table_name = get_table_name(table_name)

        attribute_definitions = t["Properties"]["AttributeDefinitions"]
        key_schema = t["Properties"]["KeySchema"]

        try:
            dynamodb.create_table(
                AttributeDefinitions=attribute_definitions,
                KeySchema=key_schema,
                TableName=table_name,
                ProvisionedThroughput={  # ignored locally, but required
                    "ReadCapacityUnits": 1,
                    "WriteCapacityUnits": 1,
                },
            )

            if logger:
                logger.info(f"Created {table_name}")
        except ClientError:
            if logger:
                logger.info(f"{table_name} already exists")


if __name__ == "__main__":
    setup_dynamo(logger)
    sync_prompts(logger)  # automatically load prompts upon set up
