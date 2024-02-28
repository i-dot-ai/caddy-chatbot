from typing import Union
from datetime import datetime
import json
import os
import uuid
import boto3
import pydantic

# === Data Models ===
class UserMessage(pydantic.BaseModel):
    message_id: Union[str, None] = None
    conversation_id: Union[str, None] = None
    thread_id: Union[str, None] = None
    message_id: Union[str, None] = None
    client: str
    user_email: str
    message: str
    message_sent_timestamp: str
    message_received_timestamp: datetime

class LlmResponse(pydantic.BaseModel):
    response_id: str = str(uuid.uuid4())
    message_id: str
    thread_id: str
    llm_prompt: str
    llm_answer: str
    llm_response_json: pydantic.Json
    llm_prompt_timestamp: datetime
    llm_response_timestamp: datetime

class SupervisionEvent(pydantic.BaseModel):
    type: str
    user: str
    llmPrompt: str
    llm_answer: str
    llm_response_json: pydantic.Json
    conversation_id: str
    thread_id: str
    message_id: str
    approver_received_timestamp: Union[datetime, None] = None
    response_id: str

class ApprovalEvent(pydantic.BaseModel):
    response_id: str
    approver_email: str
    approved: Union[bool, None] = None
    approval_timestamp: Union[datetime, None] = None
    user_response_timestamp: datetime
    supervisor_message: Union[str, None] = None

class ProcessChatMessageEvent(pydantic.BaseModel):
    type: str
    user: str
    name: str
    space_id: str
    thread_id: str
    message_id: str
    message_string: str
    source_client: str
    timestamp: datetime


# === Database functions ===
def store_message(message: UserMessage, table):
    # Storing in DynamoDB
    response = table.put_item(
        Item={
            'messageId': str(message.message_id),
            'conversationId': str(message.conversation_id),
            'threadId': str(message.thread_id),
            'client': message.client,
            'userEmail': str(message.user_email),
            'message': message.message,
            'messageSentTimestamp': message.message_sent_timestamp,
            'messageReceivedTimestamp': str(message.message_received_timestamp),
        }
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Message stored successfully!'})
    }


def store_response(response: LlmResponse, table):
    # Storing in DynamoDB
    response = table.put_item(
        Item={
            'responseId': str(response.response_id),
            'messageId': str(response.message_id),
            'threadId': str(response.thread_id),
            'llmPrompt': response.llm_prompt,
            'llmAnswer': response.llm_answer,
            'llmResponseJSon': response.llm_response_json,
            'llmPromptTimestamp': str(response.llm_prompt_timestamp),
            'llmResponseTimestamp': str(response.llm_response_timestamp),
        }
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Response stored successfully!'})
    }


def store_user_thanked_timestamp(ai_answer: LlmResponse, timestamp, table):
    # Updating response in DynamoDB
    response = table.update_item(
        Key={"threadId": ai_answer.thread_id},
        UpdateExpression="set userThankedTimestamp=:t",
        ExpressionAttributeValues={":t": str(timestamp)},
        ReturnValues="UPDATED_NEW",
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Timestamp stored successfully!'})
    }


def create_db_message_table(connection):
    """Creates the messages table in the database"""

    table = connection.create_table(
        TableName='caddyMessages',
        KeySchema=[
            {'AttributeName': 'messageId', 'KeyType': 'HASH'},  # Partition key
            {'AttributeName': 'threadId', 'KeyType': 'RANGE'},  # Sort key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'messageId', 'AttributeType': 'S'},
            {'AttributeName': 'threadId', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "gsiIndex",
                "KeySchema": [
                    {"AttributeName": "threadId", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    'ReadCapacityUnits': 10,
                    'WriteCapacityUnits': 10
                },
            },
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        },
        StreamSpecification={
            'StreamEnabled': True,
            'StreamViewType': 'NEW_AND_OLD_IMAGES'
        }
    )


def create_db_responses_table(connection):
    """Creates the responses table in the database"""

    table = connection.create_table(
        TableName='caddyResponses',
        KeySchema=[
            {'AttributeName': 'threadId', 'KeyType': 'HASH'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'threadId', 'AttributeType': 'S'},
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        }
    )


# === Database Connections ===
dynamodb = boto3.resource('dynamodb', region_name='eu-west-2')

try:
    create_db_message_table(dynamodb)
except:
    print('message table already exists')

try:
    create_db_responses_table(dynamodb)
except:
    print('response table already exists')


message_table = dynamodb.Table(os.getenv('MESSAGES_TABLE_NAME'))
users_table = dynamodb.Table(os.getenv('USERS_TABLE_NAME'))
responses_table = dynamodb.Table(os.getenv('RESPONSES_TABLE_NAME'))
idempotent_table = dynamodb.Table(os.getenv('IDEMPOTENCY_TABLE_NAME'))
