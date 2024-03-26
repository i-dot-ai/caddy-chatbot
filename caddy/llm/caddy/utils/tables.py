import boto3
import os

# === Database Connections ===
dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")

# === Tables ===
message_table = dynamodb.Table(os.getenv("MESSAGES_TABLE_NAME"))
users_table = dynamodb.Table(os.getenv("USERS_TABLE_NAME"))
responses_table = dynamodb.Table(os.getenv("RESPONSES_TABLE_NAME"))
offices_table = dynamodb.Table(os.getenv("OFFICES_TABLE_NAME"))
evaluation_table = dynamodb.Table(os.getenv("EVALUATION_TABLE_NAME"))
