from datetime import datetime
from fastapi.responses import Response
from fastapi import status

from caddy_core.models.core import (
    ProcessChatMessageEvent,
    UserMessage,
    LlmResponse,
    SupervisionEvent,
    ApprovalEvent,
)

from caddy_core.utils.core import format_chat_history
from caddy_core.utils.tables import evaluation_table, message_table, responses_table
from caddy_core.services.core import build_chain, run_chain
from caddy_core.services import enrolment
from caddy_core.services.evaluation.core import execute_optional_modules
from boto3.dynamodb.conditions import Key

import json

from typing import List, Any, Dict, Tuple


def handle_message(caddy_message, chat_client):
    existing_call, values, survey_complete = check_existing_call(
        caddy_message.thread_id
    )

    if survey_complete is True:
        chat_client.update_message_in_adviser_space(
            space_id=caddy_message.space_id,
            message_id=caddy_message.message_id,
            message=chat_client.messages["SURVEY_ALREADY_COMPLETED"],
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if existing_call is False:
        (
            modules_to_use,
            module_outputs_json,
            continue_conversation,
            control_group_message,
        ) = execute_optional_modules(
            caddy_message, execution_time="before_message_processed"
        )
        store_evaluation_module(
            thread_id=caddy_message.thread_id,
            user_arguments=modules_to_use[0],
            argument_output=module_outputs_json,
            continue_conversation=continue_conversation,
            control_group_message=control_group_message,
        )
    elif existing_call is True:
        modules_to_use = values["modulesUsed"]
        module_outputs_json = values["moduleOutputs"]
        continue_conversation = values["continueConversation"]
        control_group_message = values["controlGroupMessage"]

    message_query = format_chat_message(caddy_message)

    store_message(message_query)

    if continue_conversation is False:
        mark_call_complete(message_query.thread_id)
        chat_client.update_message_in_adviser_space(
            message_query.conversation_id,
            message_query.message_id,
            {"text": control_group_message},
        )
        if survey_complete is False:
            chat_client.run_new_survey(
                message_query.user_email,
                message_query.thread_id,
                message_query.conversation_id,
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    module_outputs_json = json.loads(module_outputs_json)
    for output in module_outputs_json.values():
        if isinstance(output, dict) and output.get("end_interaction"):
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    chat_client.update_message_in_adviser_space(
        space_id=message_query.conversation_id,
        message_id=message_query.message_id,
        message=chat_client.messages["GENERATING_RESPONSE"],
    )

    send_to_llm(caddy_query=message_query, chat_client=chat_client)


def get_chat_history(message: UserMessage) -> List:
    """
    Retrieves chats from the same thread

    Args:
        message (UserMessage): user message

    Returns:
        history (list): list of chat history
    """
    response = responses_table.query(
        KeyConditionExpression=Key("threadId").eq(message.thread_id),
    )
    history = format_chat_history(response["Items"])
    return history


def mark_call_complete(thread_id: str) -> None:
    """
    Mark the call as complete in the evaluation table

    Args:
        thread_id (str): The thread id of the conversation

    Returns:
        None
    """
    evaluation_table.update_item(
        Key={"threadId": thread_id},
        UpdateExpression="set callComplete = :cc",
        ExpressionAttributeValues={":cc": True},
    )


def format_chat_message(event: ProcessChatMessageEvent) -> UserMessage:
    """
    Formats the chat message into a UserMessage object

    Args:
        event (ProcessChatMessageEvent): The event containing the chat message

    Returns:
        UserMessage: The formatted chat message
    """
    message_query = UserMessage(
        conversation_id=event.space_id,
        thread_id=event.thread_id,
        message_id=event.message_id,
        client=event.source_client,
        user_email=event.user,
        message=event.message_string,
        message_sent_timestamp=str(event.timestamp),
        message_received_timestamp=datetime.now(),
    )

    return message_query


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


def store_user_thanked_timestamp(ai_answer: LlmResponse):
    # Updating response in DynamoDB
    responses_table.update_item(
        Key={"threadId": ai_answer.thread_id},
        UpdateExpression="set userThankedTimestamp=:t",
        ExpressionAttributeValues={":t": str(datetime.now())},
        ReturnValues="UPDATED_NEW",
    )


def store_evaluation_module(
    thread_id,
    user_arguments,
    argument_output,
    continue_conversation,
    control_group_message,
):
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
    )

    return supervision_event


def check_existing_call(threadId: str) -> Tuple[bool, Dict[str, Any], bool]:
    """
    Check if the call has already received evaluation modules

    Args:
        threadId (str): The threadId of the conversation

    Returns:
        Tuple[bool, Dict[str, Any], bool]: A tuple containing three values:
            - True if the call has already received evaluation modules, False otherwise
            - A dictionary containing the values of user_arguments, argument_output, continue_conversation, and control_group_message
            - True if the survey is complete, False otherwise
    """
    response = evaluation_table.query(
        KeyConditionExpression=Key("threadId").eq(threadId),
    )
    survey_complete = False
    if response["Items"]:
        values = {
            "modulesUsed": response["Items"][0]["modulesUsed"],
            "moduleOutputs": response["Items"][0]["moduleOutputs"],
            "continueConversation": response["Items"][0]["continueConversation"],
            "controlGroupMessage": response["Items"][0]["controlGroupMessage"],
        }
        if "surveyResponse" in response["Items"][0]:
            survey_complete = True
        return True, values, survey_complete
    return False, {}, survey_complete


def send_to_llm(caddy_query: UserMessage, chat_client):
    chat_history = get_chat_history(caddy_query)

    llm_response, source_documents = query_llm(caddy_query, chat_history)

    response_card = chat_client.create_card(llm_response, source_documents)
    response_card = json.dumps(response_card)

    llm_response.llm_response_json = response_card

    store_response(llm_response)

    supervision_event = format_supervision_event(caddy_query, llm_response)

    chat_client.update_message_in_adviser_space(
        space_id=caddy_query.conversation_id,
        message_id=caddy_query.message_id,
        message=chat_client.messages["AWAITING_APPROVAL"],
    )

    send_for_supervisor_approval(
        event=supervision_event, user=caddy_query.user_email, chat_client=chat_client
    )

    store_user_thanked_timestamp(llm_response)


def send_for_supervisor_approval(event, user, chat_client):
    supervisor_space = enrolment.get_designated_supervisor_space(user)

    if supervisor_space == "Unknown":
        raise Exception("supervision space returned unknown")

    chat_client.handle_new_supervision_event(user, supervisor_space, event)

    store_approver_received_timestamp(event)


def store_approver_received_timestamp(event: SupervisionEvent):
    # Updating response in DynamoDB
    responses_table.update_item(
        Key={"threadId": event.thread_id},
        UpdateExpression="set approverReceivedTimestamp=:t",
        ExpressionAttributeValues={":t": str(datetime.now())},
        ReturnValues="UPDATED_NEW",
    )


def store_approver_event(approval_event: ApprovalEvent):
    # Updating response in DynamoDB
    responses_table.update_item(
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
