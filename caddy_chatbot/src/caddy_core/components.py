import json
import os
from datetime import datetime
from time import sleep
from typing import Any, Dict, List, Tuple

from boto3.dynamodb.conditions import Key
from caddy_core.models import (
    ApprovalEvent,
    CaddyMessageEvent,
    LlmResponse,
    ProcessChatMessageEvent,
    SupervisionEvent,
    UserMessage,
)
from caddy_core.services import enrolment
from caddy_core.services.evaluation import execute_optional_modules
from caddy_core.services.retrieval_chain import build_chain
from caddy_core.utils.monitoring import logger
from caddy_core.utils.prompt import get_prompt, retrieve_route_specific_augmentation
from caddy_core.utils.tables import (
    evaluation_table,
    responses_table,
    users_table,
)
from caddy_core.utils.prompts.rewording_query import query_length_prompts
from fastapi import status
from fastapi.responses import Response
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import BedrockChat
from pytz import timezone


def rct_survey_reminder(event, user_record, chat_client):
    """
    When a user has an existing call remind them to complete survey
    """
    call_start_time = user_record["callStart"]
    survey_thread_id = user_record["activeThreadId"]
    space_id = event["space"]["name"].split("/")[1]
    thread_id = None
    if "thread" in event["message"]:
        thread_id = event["message"]["thread"]["name"].split("/")[3]
    chat_client.send_existing_call_reminder(
        space_id, thread_id, call_start_time, survey_thread_id, event
    )


def handle_message(caddy_message, chat_client):
    logger.info("Running message handler")
    module_values, survey_complete = check_existing_call(caddy_message)

    if survey_complete is True:
        chat_client.update_message_in_adviser_space(
            message_type="text",
            space_id=caddy_message.space_id,
            message_id=caddy_message.message_id,
            message=chat_client.messages.SURVEY_ALREADY_COMPLETED,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    module_outputs_json = module_values["moduleOutputs"]
    continue_conversation = module_values["continueConversation"]
    control_group_message = module_values["controlGroupMessage"]

    message_query = format_chat_message(caddy_message)

    store_message(message_query)

    if continue_conversation is False:
        control_group_card = chat_client.responses.control_group_selection(
            control_group_message, caddy_message
        )
        chat_client.update_message_in_adviser_space(
            message_type="cardsV2",
            space_id=message_query.conversation_id,
            message_id=message_query.message_id,
            message=control_group_card,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    module_outputs_json = json.loads(module_outputs_json)
    for output in module_outputs_json.values():
        if isinstance(output, dict) and output.get("end_interaction"):
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    chat_client.update_message_in_adviser_space(
        message_type="cardsV2",
        space_id=message_query.conversation_id,
        message_id=message_query.message_id,
        message=chat_client.messages.COMPOSING_MESSAGE,
    )

    send_to_llm(caddy_query=message_query, chat_client=chat_client, query_length_prompts=query_length_prompts)


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
        logger.info("Removing role played response")
        return True, response[:adviser_index].strip()

    adviser_index = response.find("Advisor: ")
    if adviser_index != -1:
        logger.info("Removing role played response")
        return True, response[:adviser_index].strip()

    return False, response.strip()


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
        human = message.get("llmPrompt")
        ai = message.get("llmAnswer")

        if human and ai:
            history_langchain_format.append((human, ai))
        elif human:
            history_langchain_format.append((human, ""))

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

    sorted_items = sorted(
        response["Items"],
        key=lambda x: x.get(
            "messageReceivedTimestamp", x.get("llmPromptTimestamp", "")
        ),
    )

    history = format_chat_history(sorted_items)
    return history


def mark_call_complete(user: str, thread_id: str) -> None:
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
    users_table.update_item(
        Key={"userEmail": user},
        UpdateExpression="set activeCall = :ac",
        ExpressionAttributeValues={":ac": False},
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


def format_teams_message(event: CaddyMessageEvent) -> UserMessage:
    """
    Formats the teams message into a UserMessage object

    Args:
        event (ProcessChatMessageEvent): The event containing the chat message

    Returns:
        UserMessage: The formatted chat message
    """
    message_query = UserMessage(
        thread_id="11111",
        conversation_id=event.teams_conversation["id"],
        message_id=event.message_id,
        client=event.source_client,
        user_email=event.user,
        message=event.message_string,
        message_sent_timestamp=str(event.timestamp),
        message_received_timestamp=datetime.now(),
    )
    return message_query


def store_message(message: UserMessage):
    responses_table.put_item(
        Item={
            "threadId": str(message.thread_id),
            "messageId": str(message.message_id),
            "conversationId": str(message.conversation_id),
            "client": message.client,
            "userEmail": str(message.user_email),
            "llmPrompt": message.message,
            "messageSentTimestamp": message.message_sent_timestamp,
            "messageReceivedTimestamp": str(message.message_received_timestamp),
        }
    )


def store_response(response: LlmResponse):
    responses_table.update_item(
        Key={"threadId": str(response.thread_id)},
        UpdateExpression="set responseId = :rId, llmAnswer = :la, llmResponseJSon = :lrj, llmPromptTimestamp = :lpt, llmResponseTimestamp = :lrt, route = :route, context = :context",
        ExpressionAttributeValues={
            ":rId": response.response_id,
            ":la": response.llm_answer,
            ":lrj": response.llm_response_json,
            ":lpt": str(response.llm_prompt_timestamp),
            ":lrt": str(response.llm_response_timestamp),
            ":route": response.route,
            ":context": response.context,
        },
    )


def store_user_thanked_timestamp(ai_answer: LlmResponse):
    responses_table.update_item(
        Key={"threadId": ai_answer.thread_id},
        UpdateExpression="set userThankedTimestamp=:t",
        ExpressionAttributeValues={":t": str(datetime.now())},
        ReturnValues="UPDATED_NEW",
    )


def store_evaluation_module(user, thread_id, module_values):
    user_arguments = module_values["modulesUsed"][0]
    argument_output = module_values["moduleOutputs"]
    continue_conversation = module_values["continueConversation"]
    control_group_message = module_values["controlGroupMessage"]
    # Handles DynamoDB TypeError: Float types are not supported.
    user_arguments["module_arguments"]["split"] = str(
        user_arguments["module_arguments"]["split"]
    )
    call_start_time = datetime.now(
        timezone("Europe/London")).strftime("%d-%m-%Y %H:%M")
    evaluation_table.put_item(
        Item={
            "threadId": thread_id,
            "callStart": call_start_time,
            "modulesUsed": user_arguments,
            "moduleOutputs": argument_output,
            "continueConversation": continue_conversation,
            "controlGroupMessage": control_group_message,
            "callComplete": False,
        }
    )
    users_table.update_item(
        Key={"userEmail": user},
        UpdateExpression="set activeCall = :ac, callStart = :cs, activeThreadId = :ati, modulesUsed = :mu, moduleOutputs = :mo, continueConversation = :cc, controlGroupMessage = :cg",
        ExpressionAttributeValues={
            ":ac": True,
            ":cs": call_start_time,
            ":ati": thread_id,
            ":mu": user_arguments,
            ":mo": argument_output,
            ":cc": continue_conversation,
            ":cg": control_group_message,
        },
    )


def check_existing_call(caddy_message) -> Tuple[Dict[str, Any], bool]:
    """
    Check if the user is in a call and whether call has already received evaluation modules, if not it creates them

    Args:
        user (str): The user
        threadId (str): The threadId of the conversation

    Returns:
        Tuple[Dict[str, Any], bool]: A tuple containing four values:
            - A dictionary containing the values of user_arguments, argument_output, continue_conversation, and control_group_message
            - True if the survey is complete, False otherwise
    """
    survey_complete = False
    module_values = {}
    user_response = users_table.get_item(Key={"userEmail": caddy_message.user})
    if "Item" in user_response and user_response["Item"]["activeCall"] is True:
        response = evaluation_table.query(
            KeyConditionExpression=Key("threadId").eq(caddy_message.thread_id),
        )
        if response["Items"]:
            module_values = {
                "modulesUsed": response["Items"][0]["modulesUsed"],
                "moduleOutputs": response["Items"][0]["moduleOutputs"],
                "continueConversation": response["Items"][0]["continueConversation"],
                "controlGroupMessage": response["Items"][0]["controlGroupMessage"],
            }
            if "surveyResponse" in response["Items"][0]:
                survey_complete = True
            return module_values, survey_complete
        user_active_response = users_table.get_item(
            Key={"userEmail": caddy_message.user}
        )
        if "Item" in user_active_response:
            module_values = {
                "modulesUsed": user_active_response["Item"]["modulesUsed"],
                "moduleOutputs": user_active_response["Item"]["moduleOutputs"],
                "continueConversation": user_active_response["Item"][
                    "continueConversation"
                ],
                "controlGroupMessage": user_active_response["Item"][
                    "controlGroupMessage"
                ],
            }
            survey_complete = False
        return module_values, survey_complete

    module_values = execute_optional_modules(
        caddy_message, execution_time="before_message_processed"
    )
    store_evaluation_module(
        user=caddy_message.user,
        thread_id=caddy_message.thread_id,
        module_values=module_values,
    )
    return module_values, survey_complete


def reword_advisor_query(query: str, query_length_prompts: dict) -> str:
    """A rewording agent to reword the initial incoming query.
    It does this via two prompts for the different tail length, leaving queries in middle alone
    
    Args:
        query (str): incoming query from advisor
        query_length_prompts (dict): a dict for the two prompts for either tail length
        
    Returns:
        str: Rewritten query for RAG processing.
    """

    llm = BedrockChat(
        model_id=os.getenv("LLM"),
        region_name="eu-west-3",
        model_kwargs={"temperature": 0.3, "top_k": 5, "max_tokens": 2000},
    )

    if len(query) < 50:
        prompt = query_length_prompts['0 to 50']
    elif len(query) > 400:
        prompt = query_length_prompts['400+']
    else:
        return query  # Return original if length is in range 50 to 400

    prompt += f"\n\n Incoming query is: {query}"
    response = llm.invoke(prompt)
    return response.content




def reword_advisor_message(message: str) -> str:
    llm = BedrockChat(
        model_id=os.getenv("LLM"),
        region_name="eu-west-3",
        model_kwargs={"temperature": 0.3, "top_k": 5, "max_tokens": 2000},
    )
    prompt = f"""You are an information extraction assistant called Caddy. 
    Your task is to analyze the given message and extract key information that would be relevant 
    for a legal assistance chatbot to perform a RAG (Retrieval-Augmented Generation) search. 
    Follow these guidelines: 
        1. Identify the main legal topic or issue being discussed. 
        2. Extract any specific questions being asked. 
        3. Note any relevant personal details of the individual involved (e.g., age, nationality, employment status). 
        4. Identify key facts or circumstances related to the legal situation. 
        5. Extract any mentioned dates, locations, or monetary amounts.
        6. Identify any legal terms or concepts mentioned. 
    Provide your response in a structured format with clear headings for each category of extracted information. 
    If any category is not applicable or no relevant information is found skip it. 
    Remember to focus only on extracting factual information without adding any interpretation or advice. 
    
    Input:
    {message}
    
    Extracted Information:
    """
    response = llm.invoke(prompt)
    return response.content


def send_to_llm(caddy_query: UserMessage, chat_client, query_length_prompts):
    query = caddy_query.message

    query = reword_advisor_query(query, query_length_prompts)

    domain = caddy_query.user_email.split("@")[1]

    chat_history = get_chat_history(caddy_query)

    route_specific_augmentation, route = retrieve_route_specific_augmentation(query)

    day_date_time = datetime.now(timezone("Europe/London")).strftime(
        "%A %d %B %Y %H:%M"
    )

    _, office = enrolment.check_domain_status(domain)
    office_regions = enrolment.get_office_coverage(office)

    CADDY_PROMPT = PromptTemplate(
        template=get_prompt("CORE_PROMPT"),
        input_variables=["context", "question"],
        partial_variables={
            "route_specific_augmentation": route_specific_augmentation,
            "day_date_time": day_date_time,
            "office_regions": office_regions,
        },
    )

    chain, ai_prompt_timestamp = build_chain(CADDY_PROMPT)

    user = caddy_query.user_email

    supervisor_space = enrolment.get_designated_supervisor_space(user)
    if supervisor_space == "Unknown":
        raise Exception("supervision space returned unknown")

    (
        request_failed,
        request_processing,
        request_awaiting,
        request_approved,
        request_rejected,
    ) = chat_client.create_supervision_request_card(user, initial_query=query)

    supervision_thread_id, supervision_message_id = (
        chat_client.send_message_to_supervisor_space(
            space_id=supervisor_space, message=request_processing
        )
    )

    for attempt in range(4):
        try:
            first_chunk = True
            caddy_response = {}
            accumulated_answer = ""
            for chunk in chain.stream(
                {
                    "input": reword_advisor_message(query),
                    "chat_history": chat_history,
                }
            ):
                for key, value in chunk.items():
                    if (
                        key in caddy_response
                        and isinstance(value, str)
                        and isinstance(caddy_response[key], str)
                    ):
                        caddy_response[key] += value
                    else:
                        caddy_response[key] = value

                if "answer" in chunk:
                    if first_chunk:
                        context_sources = [document.metadata.get("source", "")
                                           for document in caddy_response.get("context", [])]
                        response_card = chat_client.create_card(
                            caddy_response["answer"], context_sources)
                        response_card["cardsV2"][0]["card"]["sections"][0][
                            "widgets"
                        ].append(chat_client.messages.RESPONSE_STREAMING)
                        supervision_caddy_message_id = (
                            chat_client.respond_to_supervisor_thread(
                                space_id=supervisor_space,
                                message=response_card,
                                thread_id=supervision_thread_id,
                            )
                        )
                        chat_client.update_message_in_adviser_space(
                            message_type="cardsV2",
                            space_id=caddy_query.conversation_id,
                            message_id=caddy_query.message_id,
                            message=chat_client.messages.SUPERVISOR_REVIEWING_RESPONSE,
                        )
                        first_chunk = None

                    accumulated_answer += chunk["answer"]
                    if len(accumulated_answer) >= 75:
                        early_terminate, caddy_response["answer"] = (
                            remove_role_played_responses(
                                caddy_response["answer"])
                        )
                        context_sources = [document.metadata.get("source", "")
                                           for document in caddy_response.get("context", [])]
                        response_card = chat_client.create_card(
                            caddy_response["answer"], context_sources)
                        response_card["cardsV2"][0]["card"]["sections"][0][
                            "widgets"
                        ].append(chat_client.messages.RESPONSE_STREAMING)
                        chat_client.update_message_in_supervisor_space(
                            space_id=supervisor_space,
                            message_id=supervision_caddy_message_id,
                            new_message=response_card,
                        )
                        accumulated_answer = ""
                        if early_terminate is True:
                            break
            break
        except Exception as error:
            print(f"Attempt {attempt+1} failed with error: {error}")
            if attempt == 3:
                chat_client.update_message_in_adviser_space(
                    message_type="cardsV2",
                    space_id=caddy_query.conversation_id,
                    message_id=caddy_query.message_id,
                    message=chat_client.messages.REQUEST_FAILURE,
                )
                chat_client.update_message_in_supervisor_space(
                    space_id=supervisor_space,
                    message_id=supervision_message_id,
                    new_message=request_failed,
                )
                raise Exception(f"Caddy failed to response, error: {error}")
            chat_client.update_message_in_adviser_space(
                message_type="cardsV2",
                space_id=caddy_query.conversation_id,
                message_id=caddy_query.message_id,
                message=chat_client.messages.COMPOSING_MESSAGE_RETRY,
            )
            wait = attempt**2
            print(f"Retrying in {wait}...")
            sleep(wait)

    _, caddy_response["answer"] = remove_role_played_responses(
        caddy_response["answer"])
    context_sources = [document.metadata.get("source", "")
                       for document in caddy_response.get("context", [])]
    response_card = chat_client.create_card(
        caddy_response["answer"], context_sources)
    chat_client.update_message_in_supervisor_space(
        space_id=supervisor_space,
        message_id=supervision_caddy_message_id,
        new_message=response_card,
    )

    ai_response_timestamp = datetime.now()

    logger.info(context_sources)

    llm_response = LlmResponse(
        message_id=caddy_query.message_id,
        llm_prompt=caddy_query.message,
        llm_answer=caddy_response["answer"],
        thread_id=caddy_query.thread_id,
        llm_prompt_timestamp=ai_prompt_timestamp,
        llm_response_json=json.dumps(response_card),
        llm_response_timestamp=ai_response_timestamp,
        route=route or "no_route",
        context=context_sources,
    )

    store_response(llm_response)

    supervision_event = SupervisionEvent(
        type="SUPERVISION_REQUIRED",
        source_client=caddy_query.client,
        user=caddy_query.user_email,
        llmPrompt=llm_response.llm_prompt,
        llm_answer=llm_response.llm_answer,
        llm_response_json=json.dumps(llm_response.llm_response_json),
        conversation_id=caddy_query.conversation_id,
        thread_id=caddy_query.thread_id,
        message_id=caddy_query.message_id,
        response_id=str(llm_response.response_id),
    )

    chat_client.update_message_in_adviser_space(
        message_type="cardsV2",
        space_id=caddy_query.conversation_id,
        message_id=caddy_query.message_id,
        message=chat_client.messages.AWAITING_SUPERVISOR_APPROVAL,
    )
    store_user_thanked_timestamp(llm_response)

    chat_client.update_message_in_supervisor_space(
        space_id=supervisor_space,
        message_id=supervision_message_id,
        new_message=request_awaiting,
    )

    supervision_card = chat_client.create_supervision_card(
        user_email=user,
        event=supervision_event,
        new_request_message_id=supervision_message_id,
        request_approved=request_approved,
        request_rejected=request_rejected,
        card_for_approval=response_card,
    )

    chat_client.update_message_in_supervisor_space(
        space_id=supervisor_space,
        message_id=supervision_caddy_message_id,
        new_message=supervision_card,
    )

    store_approver_received_timestamp(supervision_event)


def store_approver_received_timestamp(event: SupervisionEvent):
    responses_table.update_item(
        Key={"threadId": event.thread_id},
        UpdateExpression="set approverReceivedTimestamp=:t",
        ExpressionAttributeValues={":t": str(datetime.now())},
        ReturnValues="UPDATED_NEW",
    )


def store_approver_event(thread_id: str, approval_event: ApprovalEvent):
    responses_table.update_item(
        Key={"threadId": thread_id},
        UpdateExpression="set responseId=:rId, approverEmail=:email, approved=:approved, approvalTimestamp=:atime, userResponseTimestamp=:utime, supervisorMessage=:sMessage",
        ExpressionAttributeValues={
            ":rId": approval_event.response_id,
            ":email": approval_event.approver_email,
            ":approved": approval_event.approved,
            ":atime": str(approval_event.approval_timestamp),
            ":utime": str(approval_event.user_response_timestamp),
            ":sMessage": approval_event.supervisor_message,
        },
        ReturnValues="UPDATED_NEW",
    )


def temporary_teams_invoke(chat_client, caddy_message: CaddyMessageEvent):
    """
    Temporary solution for Teams integration
    """
    store_message(format_teams_message(caddy_message))
    route_specific_augmentation, _ = retrieve_route_specific_augmentation(
        caddy_message.message_string
    )

    day_date_time = datetime.now(timezone("Europe/London")).strftime(
        "%A %d %B %Y %H:%M"
    )

    office_regions = ["England"]

    CADDY_PROMPT = PromptTemplate(
        template=get_prompt("CORE_PROMPT"),
        input_variables=["context", "question"],
        partial_variables={
            "route_specific_augmentation": route_specific_augmentation,
            "day_date_time": day_date_time,
            "office_regions": office_regions,
        },
    )

    chain, ai_prompt_timestamp = build_chain(CADDY_PROMPT)

    caddy_response = chain.invoke(
        {
            "input": reword_advisor_message(caddy_message.message_string),
            "chat_history": [],
        }
    )

    _, caddy_response["answer"] = remove_role_played_responses(caddy_response["answer"])

    chat_client.send_adviser_card(
        caddy_message,
        card=chat_client.messages.generate_response_card(caddy_response["answer"]),
    )
