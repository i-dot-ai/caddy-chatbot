import os
import json
import boto3
from typing import List, Any
from datetime import datetime
from boto3.dynamodb.conditions import Key

from caddy.services.core import run_chain, build_chain
from caddy.utils.tables import message_table, responses_table, evaluation_table
from caddy.utils.core import format_chat_history
from caddy.models.core import (
    UserMessage,
    LlmResponse,
    SupervisionEvent,
    ProcessChatMessageEvent,
)

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

serverless = boto3.client("lambda")


@xray_recorder.capture()
def send_for_supervisor_approval(supervision_event: SupervisionEvent):
    serverless.invoke(
        FunctionName=f'supervise-{os.getenv("STAGE")}',
        InvocationType="Event",
        Payload=supervision_event,
    )


@xray_recorder.capture()
def format_chat_message(
    event: ProcessChatMessageEvent, modules_to_use, module_outputs_json
):
    message_query = UserMessage(
        conversation_id=event["space_id"],
        thread_id=event["thread_id"],
        message_id=event["message_id"],
        client=event["source_client"],
        user_email=event["user"],
        message=event["message_string"],
        message_sent_timestamp=event["timestamp"],
        message_received_timestamp=datetime.now(),
    )

    return message_query


@xray_recorder.capture()
def store_message(message: UserMessage):
    message_table.put_item(
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


@xray_recorder.capture()
def store_response(response: LlmResponse):
    responses_table.put_item(
        Item={
            "responseId": str(response.response_id),
            "messageId": str(response.message_id),
            "threadId": str(response.thread_id),
            "llmPrompt": response.llm_prompt,
            "llmAnswer": response.llm_answer,
            "llmResponseJSon": response.llm_response_json,
            "llmPromptTimestamp": str(response.llm_prompt_timestamp),
            "llmResponseTimestamp": str(response.llm_response_timestamp),
        }
    )


@xray_recorder.capture()
def store_user_thanked_timestamp(ai_answer: LlmResponse):
    # Updating response in DynamoDB
    responses_table.update_item(
        Key={"threadId": ai_answer.thread_id},
        UpdateExpression="set userThankedTimestamp=:t",
        ExpressionAttributeValues={":t": str(datetime.now())},
        ReturnValues="UPDATED_NEW",
    )


@xray_recorder.capture()
def store_evaluation_module(thread_id, user_arguments, argument_output, continue_conversation, control_group_message):
    # Handles DynamoDB TypeError: Float types are not supported.
    user_arguments["module_arguments"]["split"] = str(
        user_arguments["module_arguments"]["split"]
    )

    evaluation_table.put_item(
        Item={
            "threadId": thread_id,
            "modulesUsed": user_arguments,
            "moduleOutputs": argument_output,
            "continueConversation": continue_conversation,
            "controlGroupMessage": control_group_message,
            "callComplete": False,
        }
    )


@xray_recorder.capture()
def get_chat_history(message):
    # retrieve list of messages with same conversation_id from message database
    # change to get thread messages from API
    response = responses_table.query(
        KeyConditionExpression=Key("threadId").eq(message.thread_id),
    )
    history = format_chat_history(response["Items"])
    return history


@xray_recorder.capture()
def query_llm(message_query: UserMessage, chat_history: List[Any]):
    chain, ai_prompt_timestamp = build_chain()

    ai_response, ai_response_timestamp = run_chain(
        chain, message_query.message, chat_history
    )

    source_documents = ai_response["source_documents"]

    llm_response = LlmResponse(
        message_id=message_query.message_id,
        llm_prompt=message_query.message,
        llm_answer=ai_response["result"],
        thread_id=message_query.thread_id,
        llm_prompt_timestamp=ai_prompt_timestamp,
        llm_response_timestamp=ai_response_timestamp,
    )

    return llm_response, source_documents


@xray_recorder.capture()
def format_supervision_event(message_query: UserMessage, llm_response: LlmResponse):
    supervision_event = SupervisionEvent(
        type="SUPERVISION_REQUIRED",
        source_client=message_query.client,
        user=message_query.user_email,
        llmPrompt=llm_response.llm_prompt,
        llm_answer=llm_response.llm_answer,
        llm_response_json=llm_response.llm_response_json,
        conversation_id=message_query.conversation_id,
        thread_id=message_query.thread_id,
        message_id=message_query.message_id,
        response_id=str(llm_response.response_id),
    ).model_dump_json()

    return supervision_event

def check_existing_call(threadId):
    response = evaluation_table.query(
        KeyConditionExpression=Key("threadId").eq(threadId),
    )
    survey_complete = False
    if response["Items"]:
        values = {
            "user_arguments": response["Items"][0]["user_arguments"],
            "argument_output": response["Items"][0]["argument_output"],
            "continue_conversation": response["Items"][0]["continue_conversation"],
            "control_group_message": response["Items"][0]["control_group_message"]
        }
        if "surveyResponse" in response["Items"][0]:
            survey_complete = True
        return True, values, survey_complete
    return False, {}, survey_complete