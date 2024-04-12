from datetime import datetime
from fastapi.responses import Response
from fastapi import status

from langchain.prompts import PromptTemplate
from caddy_core.utils.prompts.default_template import CADDY_PROMPT_TEMPLATE
from caddy_core.utils.prompts.prompt import retrieve_route_specific_augmentation

from caddy_core.models import (
    ProcessChatMessageEvent,
    UserMessage,
    LlmResponse,
    SupervisionEvent,
    ApprovalEvent,
)

from caddy_core.utils.tables import (
    evaluation_table,
    message_table,
    responses_table,
    users_table,
)
from caddy_core.services.retrieval_chain import build_chain, run_chain
from caddy_core.services import enrolment
from caddy_core.services.evaluation import execute_optional_modules
from boto3.dynamodb.conditions import Key

import json
from pytz import timezone

from typing import List, Any, Dict, Tuple


def handle_message(caddy_message, chat_client):
    user_active_call, call_modules, module_values, survey_complete = (
        check_existing_call(caddy_message.thread_id)
    )

    if survey_complete is True:
        chat_client.update_message_in_adviser_space(
            space_id=caddy_message.space_id,
            message_id=caddy_message.message_id,
            message=chat_client.messages.SURVEY_ALREADY_COMPLETED,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if call_modules is False:
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
    elif call_modules is True:
        modules_to_use = module_values["modulesUsed"]
        module_outputs_json = module_values["moduleOutputs"]
        continue_conversation = module_values["continueConversation"]
        control_group_message = module_values["controlGroupMessage"]

    message_query = format_chat_message(caddy_message)

    store_message(message_query)

    if user_active_call is True and continue_conversation is False:
        chat_client.update_message_in_adviser_space(
            message_query.conversation_id,
            message_query.message_id,
            {"text": f"{control_group_message}, please try again on your next call"},
        )
        chat_client.call_complete_confirmation(
            user=message_query.user_email,
            user_space=message_query.conversation_id,
            thread_id=message_query.thread_id,
        )

    if continue_conversation is False:
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
        message=chat_client.messages.GENERATING_RESPONSE,
    )

    send_to_llm(caddy_query=message_query, chat_client=chat_client)


def remove_role_played_responses(response: str) -> str:
    """
    This function checks for and cuts off the adviser output at the end of some LLM responses

    Args:
        response (str): LLM response string

    Returns:
        response (str): cleaner version of the LLM response
    """
    adviser_index = response.find("Adviser: ")

    if adviser_index != -1:
        response = response[:adviser_index]

    return response.strip()


def format_chat_history(user_messages: List) -> List:
    """
    Formats chat messages for LangChain

    Args:
        user_messages (list): list of user messages

    Returns:
        history (list): langchain formatted
    """
    history_langchain_format = []
    for message in user_messages:
        human = message["llmPrompt"]
        ai = message["llmAnswer"]
        history_langchain_format.append((human, ai))
    return history_langchain_format


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
    route_specific_augmentation = retrieve_route_specific_augmentation(
        query=message_query.message
    )

    day_date_time = datetime.now(timezone("Europe/London")).strftime(
        "%A %d %B %Y %H:%M"
    )

    office_regions = enrolment.get_office_coverage(
        message_query.user_email.split("@")[1]
    )

    CADDY_PROMPT = PromptTemplate(
        template=CADDY_PROMPT_TEMPLATE,
        input_variables=["context", "question"],
        partial_variables={
            "route_specific_augmentation": route_specific_augmentation,
            "day_date_time": day_date_time,
            "office_regions": office_regions,
        },
    )

    chain, ai_prompt_timestamp = build_chain(CADDY_PROMPT)

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

    llm_response.llm_answer = remove_role_played_responses(llm_response.llm_answer)

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


def check_existing_call(user: str, threadId: str) -> Tuple[bool, Dict[str, Any], bool]:
    """
    Check if the user is in a call and whether call has already received evaluation modules

    Args:
        user (str): The user
        threadId (str): The threadId of the conversation

    Returns:
        Tuple[bool, Dict[str, Any], bool]: A tuple containing four values:
            - True if the user is on an existing call, False if it is a new call
            - True if the call has already received evaluation modules, False otherwise
            - A dictionary containing the values of user_arguments, argument_output, continue_conversation, and control_group_message
            - True if the survey is complete, False otherwise
    """
    user_active_call = False
    call_modules = False
    survey_complete = False
    module_values = {}
    user_response = users_table.get_item(Key={"userEmail": user})
    if "Item" in user_response and user_response["Item"]["activeCall"] is True:
        user_active_call = True
        response = evaluation_table.query(
            KeyConditionExpression=Key("threadId").eq(threadId),
        )
        if response["Items"]:
            call_modules = True
            module_values = {
                "modulesUsed": response["Items"][0]["modulesUsed"],
                "moduleOutputs": response["Items"][0]["moduleOutputs"],
                "continueConversation": response["Items"][0]["continueConversation"],
                "controlGroupMessage": response["Items"][0]["controlGroupMessage"],
            }
            if "surveyResponse" in response["Items"][0]:
                survey_complete = True
            return user_active_call, call_modules, module_values, survey_complete
        return user_active_call, call_modules, module_values, survey_complete
    return user_active_call, call_modules, module_values, survey_complete


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
        message=chat_client.messages.AWAITING_APPROVAL,
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
