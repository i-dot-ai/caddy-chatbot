import boto3
import os

from dotenv import load_dotenv

load_dotenv()

dynamo_url = os.getenv("DYNAMODB_URL")
if dynamo_url:
    dynamodb = boto3.resource(
        "dynamodb", region_name="eu-west-2", endpoint_url=dynamo_url
    )
else:
    dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")

message_table = dynamodb.Table(os.getenv("MESSAGES_TABLE_NAME"))
users_table = dynamodb.Table(os.getenv("USERS_TABLE_NAME"))
responses_table = dynamodb.Table(os.getenv("RESPONSES_TABLE_NAME"))
offices_table = dynamodb.Table(os.getenv("OFFICES_TABLE_NAME"))
evaluation_table = dynamodb.Table(os.getenv("EVALUATION_TABLE_NAME"))
prompts_table = dynamodb.Table(os.getenv("PROMPTS_TABLE_NAME"))
