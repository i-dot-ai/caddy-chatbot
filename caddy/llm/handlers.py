import os
import json
from datetime import datetime
import boto3
from models import (
    UserMessage,
    LlmResponse,
    SupervisionEvent,
    ProcessChatMessageEvent,
    store_message,
    store_response,
    store_user_thanked_timestamp,
    message_table,
    responses_table,
)
from utils import create_card, get_chat_history, store_evaluation_module
from llm import run_chain, build_chain
from responses import update_message_in_adviser_space
from utils import bcolors, execute_optional_modules

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

serverless = boto3.client("lambda")


@xray_recorder.capture()
def process_chat_message(event: ProcessChatMessageEvent):
    """Takes a chat message, and converts it to a UserQuery

    Returns:
        AiResponse: The llm output
    """

    # look for any modules linked to the user workspace, and execute it.
    (
        modules_to_use,
        module_outputs_json,
        continue_conversation,
    ) = execute_optional_modules(event, execution_time="before_message_processed")

    if continue_conversation is False:
        return

    message_query = UserMessage(
        conversation_id=event["space_id"],
        thread_id=event["thread_id"],
        message_id=event["message_id"],
        client=event["source_client"],
        user_email=event["user"],
        message=event["message_string"],
        message_sent_timestamp=event["timestamp"],
        message_received_timestamp=datetime.now(),
        user_arguments=json.dumps(modules_to_use[0]),
        argument_output=module_outputs_json,
    )

    # store user message in db
    store_message(message_query, message_table)
    store_evaluation_module(
        thread_id=message_query.thread_id,
        user_arguments=message_query.user_arguments,
        argument_output=message_query.argument_output,
    )

    module_outputs_json = json.loads(module_outputs_json)

    # Check if any of the module_outputs returned "end_interaction"
    for output in module_outputs_json.values():
        if isinstance(output, dict) and output.get("end_interaction"):
            return

    chat_history = get_chat_history(message_query)

    print(
        f"{bcolors.OKGREEN} ### FORMATTED MESSAGE QUERY \n\n {message_query} \n\n ### END OF MESSAGE QUERY {bcolors.ENDC}"
    )

    update_message_in_adviser_space(
        space_id=message_query.conversation_id,
        message_id=message_query.message_id,
        message={"text": "*Status:* _*Generating response*_ "},
    )

    # query llm
    chain, ai_prompt_timestamp = build_chain()
    ai_response, ai_response_timestamp = run_chain(
        chain, message_query.message, chat_history
    )

    print(
        f"{bcolors.OKCYAN}### AI RESPONSE RECEIVED \n\n {ai_response} \n\n ### END OF AI RESPONSE{bcolors.ENDC}"
    )
    print(
        f"{bcolors.OKBLUE}### START OF AI ANSWER \n\n {ai_response['result']} \n\n ### END OF AI ANSWER{bcolors.ENDC}"
    )

    response_card = create_card(ai_response)
    response_card = json.dumps(response_card)

    ai_answer = LlmResponse(
        message_id=message_query.message_id,
        llm_prompt=message_query.message,
        llm_answer=ai_response["result"],
        thread_id=message_query.thread_id,
        llm_response_json=response_card,
        llm_prompt_timestamp=ai_prompt_timestamp,
        llm_response_timestamp=ai_response_timestamp,
    )

    # store ai response in db
    store_response(ai_answer, responses_table)

    supervision_event = SupervisionEvent(
        type="SUPERVISION_REQUIRED",
        source_client=message_query.client,
        user=message_query.user_email,
        llmPrompt=ai_answer.llm_prompt,
        llm_answer=ai_answer.llm_answer,
        llm_response_json=response_card,
        conversation_id=message_query.conversation_id,
        thread_id=message_query.thread_id,
        message_id=message_query.message_id,
        response_id=str(ai_answer.response_id),
    ).model_dump_json()

    update_message_in_adviser_space(
        space_id=message_query.conversation_id,
        message_id=message_query.message_id,
        message={"text": "*Status:* _*Awaiting supervisor approval*_ "},
    )

    store_user_thanked_timestamp(
        ai_answer, timestamp=datetime.now(), table=responses_table
    )

    print(
        f"{bcolors.OKGREEN}### START OF SUPERVISION EVENT \n\n {supervision_event} \n\n ### END OF SUPERVISION EVENT {bcolors.ENDC}"
    )

    serverless.invoke(
        FunctionName=f'supervise-{os.getenv("STAGE")}',
        InvocationType="Event",
        Payload=supervision_event,
    )
