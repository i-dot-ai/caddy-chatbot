from typing import Union
from datetime import datetime
import json
import os
import uuid
import pydantic
from pydantic.types import StrictBool
import boto3


# === Data Models ===
class UserMessage(pydantic.BaseModel):
    message_id: Union[str, None] = None
    conversation_id: Union[str, None] = None
    thread_id: Union[str, None] = None
    client: str
    user_email: str
    message: str
    message_sent_timestamp: str
    message_received_timestamp: datetime


class LlmResponse(pydantic.BaseModel):
    response_id: str = str(uuid.uuid4())
    message_id: str
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
    thread_id: str
    approver_email: str
    approved: Union[bool, None] = None
    approval_timestamp: Union[datetime, None] = None
    user_response_timestamp: datetime
    supervisor_message: Union[str, None] = None


class User(pydantic.BaseModel):
    user_email: str
    is_approver: StrictBool = False
    is_super_user: StrictBool = False
    created_at: datetime = datetime.now()
    supervision_space_id: str


# === Database functions ===
def store_message(message: UserMessage, table):
    # Storing in DynamoDB
    table.put_item(
        Item={
            "messageId": str(message.message_id),
            "conversationId": str(message.conversation_id),
            "threadId": str(message.thread_id),
            "client": message.client,
            "userEmail": str(message.user_email),
            "message": message.message,
            "messageSentTimestamp": message.message_sent_timestamp,
            "messageReceivedTimestamp": str(message.message_received_timestamp),
        }
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Message stored successfully!"}),
    }


def store_response(response: LlmResponse, table):
    # Storing in DynamoDB
    response = table.put_item(
        Item={
            "responseId": str(response.response_id),
            "messageId": str(response.message_id),
            "llmPrompt": response.llm_prompt,
            "llmAnswer": response.llm_answer,
            "llmResponseJSon": response.llm_response_json,
            "llmPromptTimestamp": str(response.llm_prompt_timestamp),
            "llmResponseTimestamp": str(response.llm_response_timestamp),
        }
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Response stored successfully!"}),
    }


def store_approver_received_timestamp(event: SupervisionEvent, timestamp, table):
    # Updating response in DynamoDB
    table.update_item(
        Key={"threadId": str(event["thread_id"])},
        UpdateExpression="set approverReceivedTimestamp=:t",
        ExpressionAttributeValues={":t": str(timestamp)},
        ReturnValues="UPDATED_NEW",
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Timestamp stored successfully!"}),
    }


def store_approver_event(approval_event: ApprovalEvent, table):
    # Updating response in DynamoDB
    table.update_item(
        Key={"threadId": str(approval_event.thread_id)},
        UpdateExpression="set approverEmail=:email, approved=:approved, approvalTimestamp=:atime, userResponseTimestamp=:utime, supervisorMessage=:sMessage",
        ExpressionAttributeValues={
            ":email": approval_event.approver_email,
            ":approved": approval_event.approved,
            ":atime": str(approval_event.approval_timestamp),
            ":utime": str(approval_event.user_response_timestamp),
            ":sMessage": approval_event.supervisor_message,
        },
        ReturnValues="UPDATED_NEW",
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "Supervisor approval/ rejection stored successfully!"}
        ),
    }


# === Database Connections ===

dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")

message_table = dynamodb.Table(os.getenv("MESSAGES_TABLE_NAME"))
responses_table = dynamodb.Table(os.getenv("RESPONSES_TABLE_NAME"))
offices_table = dynamodb.Table(os.getenv("OFFICES_TABLE_NAME"))
users_table = dynamodb.Table(os.getenv("USERS_TABLE_NAME"))
evaluation_table = dynamodb.Table(os.getenv("EVALUATION_TABLE_NAME"))
