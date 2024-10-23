import sys

from botocore.exceptions import ClientError
from cfn_tools import load_yaml
from dotenv import load_dotenv

sys.path.append("caddy_chatbot/src")

from caddy_core.hosting_environment import HostingEnvironment
from caddy_core.utils.tables import dynamodb

load_dotenv()


def setup_dynamo():
    if not HostingEnvironment.is_dev():
        raise Exception("Refusing to run setup_dynamo in non-dev environment")

    raw_yaml = open("infra/template.yaml").read()
    cloudformation = load_yaml(raw_yaml)

    tables = {
        k: v
        for k, v in cloudformation["Resources"].items()
        if v["Type"] == "AWS::DynamoDB::Table"
    }

    for k, t in tables.items():
        table_name = k
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
            print(f"Created {table_name}")
        except ClientError:
            print(f"{table_name} already exists")


if __name__ == "__main__":
    setup_dynamo()
