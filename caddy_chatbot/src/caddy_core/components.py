import json
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple, Union, Optional

from boto3.dynamodb.conditions import Key
from caddy_core.models import (
    ApprovalEvent,
    CaddyMessageEvent,
    LlmResponse,
    ProcessChatMessageEvent,
    SupervisionEvent,
    UserMessage,
    LLMOutput,
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
from langchain_aws import ChatBedrock
from pytz import timezone

from langchain.output_parsers import PydanticOutputParser, RetryOutputParser


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
    logger.debug("Running message handler")
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

    send_to_llm(
        caddy_query=message_query,
        chat_client=chat_client,
    )


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
        logger.debug("Removing role played response")
        return True, response[:adviser_index].strip()

    adviser_index = response.find("Advisor: ")
    if adviser_index != -1:
        logger.debug("Removing role played response")
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


def format_teams_user_message(event: CaddyMessageEvent) -> UserMessage:
    """
    Formats the teams message into a UserMessage object

    Args:
        event (ProcessChatMessageEvent): The event containing the chat message

    Returns:
        UserMessage: The formatted chat message
    """
    message_query = UserMessage(
        thread_id=event.message_id,
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
    call_start_time = datetime.now(timezone("Europe/London")).strftime("%d-%m-%Y %H:%M")
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


def reword_advisor_orchestration(query: str, query_length_prompts: dict) -> str:
    """An agent to reason whether the reworded query is sufficient.
    It does this via two prompts for the different tail length, leaving queries in middle alone

    Args:
        query (str): incoming query from advisor
        query_length_prompts (dict): a dict for the two prompts for either tail length

    Returns:
        str: Rewritten query for RAG processing.
    """

    reworded_query = reword_advisor_message(query)

    if 50 <= len(reworded_query) <= 200:
        return reworded_query  # no flag

    llm = ChatBedrock(
        model_id=os.getenv("AGENT_LLM"),
        region_name="eu-west-3",
        model_kwargs={"temperature": 0, "top_k": 5, "max_tokens": 2000},
    )

    prompt = (
        query_length_prompts["0 to 50"]
        if len(reworded_query) < 50
        else query_length_prompts["400+"]
    )
    prompt += f"\n\nIncoming rewritten query: {reworded_query}"

    content = llm.invoke(prompt).content

    logger.debug(f"content: {content}")

    return content


def reword_advisor_message(message: str) -> str:
    llm = ChatBedrock(
        model_id=os.getenv("AGENT_LLM"),
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

    logger.debug(f"reworded query: {response}")

    return response.content


def send_to_llm(
    caddy_query: UserMessage,
    chat_client,
    is_follow_up=False,
    follow_up_context="",
    supervisor_message_id: Optional[str] = None,
    supervisor_thread_id: Optional[str] = None,
):
    query = caddy_query.message
    domain = caddy_query.user_email.split("@")[1]
    chat_history = get_chat_history(caddy_query)
    route_specific_augmentation, route = retrieve_route_specific_augmentation(query)
    day_date_time = datetime.now(timezone("Europe/London")).strftime(
        "%A %d %B %Y %H:%M"
    )
    _, office = enrolment.check_domain_status(domain)
    office_regions = enrolment.get_office_coverage(office)

    llm = ChatBedrock(
        model_id=os.getenv("AGENT_LLM"),
        region_name="eu-west-3",
        model_kwargs={"temperature": 0, "top_k": 5},
    )

    if is_follow_up:
        prompt_template = (
            get_prompt("CORE_PROMPT")
            + f"\nImportant context for client circumstances to consider in the advice and follow up steps, do not suggest the same questions:\n{follow_up_context}. \n\n Ensure to follow all formatting instructions and diverse inline citations and helpful resource links."
        )
        CADDY_PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "input"],
            partial_variables={
                "route_specific_augmentation": route_specific_augmentation,
                "day_date_time": day_date_time,
                "office_regions": ", ".join(office_regions),
            },
        )
    else:
        parser = PydanticOutputParser(pydantic_object=LLMOutput)
        retry_parser = RetryOutputParser.from_llm(parser=parser, llm=llm)
        prompt_template = (
            get_prompt("CORE_PROMPT")
            + "\n{format_instructions}\n respond with json only - no other text"
        )
        CADDY_PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "input"],
            partial_variables={
                "route_specific_augmentation": route_specific_augmentation,
                "day_date_time": day_date_time,
                "office_regions": ", ".join(office_regions),
                "format_instructions": parser.get_format_instructions(),
            },
        )

    chain, ai_prompt_timestamp = build_chain(CADDY_PROMPT, user=caddy_query.user_email)

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
        request_follow_up,
    ) = chat_client.create_supervision_request_card(user, initial_query=query)

    if not is_follow_up:
        supervision_thread_id, supervisor_message_id = (
            chat_client.send_message_to_supervisor_space(
                space_id=supervisor_space, message=request_processing
            )
        )
    else:
        supervision_thread_id = supervisor_thread_id
        if supervisor_message_id is None or supervision_thread_id is None:
            raise ValueError(
                "supervisor_message_id and supervisor_thread_id are required for follow-up responses"
            )

    try:
        logger.debug(f"additional context: {follow_up_context}")
        input_query = (
            query
            if not is_follow_up
            else f"{query}\n\nAdditional context:\n{follow_up_context}"
        )
        reworded_query = reword_advisor_orchestration(input_query, query_length_prompts)

        caddy_response = chain.invoke(
            {
                "input": reworded_query,
                "chat_history": chat_history,
            }
        )

        context_sources = [
            document.metadata.get("source", "")
            for document in caddy_response.get("context", [])
        ]
        logger.debug(f"SOURCES: {context_sources}")

        if is_follow_up:
            llm_output = LLMOutput(
                message=caddy_response["answer"], follow_up_questions=[]
            )
        else:
            prompt_value = CADDY_PROMPT.format_prompt(
                context=caddy_response.get("context", []), input=reworded_query
            )
            llm_output = retry_parser.parse_with_prompt(
                caddy_response["answer"], prompt_value
            )

        if llm_output.follow_up_questions and not is_follow_up:
            follow_up_card = chat_client.responses.create_follow_up_questions_card(
                llm_output, caddy_query, supervisor_message_id, supervision_thread_id
            )
            chat_client.update_message_in_adviser_space(
                message_type="cardsV2",
                space_id=caddy_query.conversation_id,
                message_id=caddy_query.message_id,
                message=follow_up_card,
            )
            chat_client.update_message_in_supervisor_space(
                space_id=supervisor_space,
                message_id=supervisor_message_id,
                new_message=request_follow_up,
            )
            return chat_client.responses.NO_CONTENT

        _, llm_output.message = remove_role_played_responses(llm_output.message)

        logger.debug(f"LLM: {llm_output.message}")
        response_card = chat_client.create_card(llm_output.message, context_sources)

        supervision_caddy_message_id = chat_client.respond_to_supervisor_thread(
            space_id=supervisor_space,
            message=response_card,
            thread_id=supervision_thread_id,
        )

        chat_client.update_message_in_supervisor_space(
            space_id=supervisor_space,
            message_id=supervisor_message_id,
            new_message=request_awaiting,
        )

        chat_client.update_message_in_adviser_space(
            message_type="cardsV2",
            space_id=caddy_query.conversation_id,
            message_id=caddy_query.message_id,
            message=chat_client.messages.SUPERVISOR_REVIEWING_RESPONSE,
        )

    except Exception as error:
        logger.error(f"Error in send_to_llm: {str(error)}")
        chat_client.update_message_in_adviser_space(
            message_type="cardsV2",
            space_id=caddy_query.conversation_id,
            message_id=caddy_query.message_id,
            message=chat_client.messages.REQUEST_FAILURE,
        )
        if not is_follow_up:
            chat_client.update_message_in_supervisor_space(
                space_id=supervisor_space,
                message_id=supervisor_message_id,
                new_message=request_failed,
            )
        raise Exception(f"Caddy response failed: {error}")

    ai_response_timestamp = datetime.now()

    logger.debug(f"SOURCES: {context_sources}")

    llm_response = LlmResponse(
        message_id=caddy_query.message_id,
        llm_prompt=caddy_query.message,
        llm_answer=llm_output.message,
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
        message_id=supervisor_message_id,
        new_message=request_awaiting,
    )

    supervision_card = chat_client.create_supervision_card(
        user_email=user,
        event=supervision_event,
        new_request_message_id=supervisor_message_id,
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


def store_approver_received_timestamp(
    event: Union[SupervisionEvent, CaddyMessageEvent],
):
    thread_id = event.thread_id if hasattr(event, "thread_id") else event.message_id

    responses_table.update_item(
        Key={"threadId": str(thread_id)},
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


def store_user_thanked_timestamp_teams(user_message: UserMessage):
    responses_table.update_item(
        Key={"threadId": user_message.thread_id},
        UpdateExpression="set userThankedTimestamp=:t",
        ExpressionAttributeValues={":t": str(datetime.now())},
        ReturnValues="UPDATED_NEW",
    )


async def temporary_teams_invoke(chat_client, caddy_event: CaddyMessageEvent):
    """
    Temporary solution for Teams integration with status updates
    """
    status_activity_id = await chat_client.send_status_update(caddy_event, "processing")

    caddy_user_message = format_teams_user_message(caddy_event)
    store_message(caddy_user_message)
    store_user_thanked_timestamp_teams(caddy_user_message)
    route_specific_augmentation, route = retrieve_route_specific_augmentation(
        caddy_event.message_string
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

    await chat_client.send_status_update(caddy_event, "composing", status_activity_id)

    try:
        caddy_response = await chain.ainvoke(
            {
                "input": reword_advisor_orchestration(
                    caddy_event.message_string, query_length_prompts
                ),
                "chat_history": [],
            }
        )
    except Exception as e:
        logger.error(f"Error invoking chain: {str(e)}")
        await chat_client.send_status_update(
            caddy_event, "request_failure", status_activity_id
        )
        return None, None

    _, caddy_response["answer"] = remove_role_played_responses(caddy_response["answer"])

    context_sources = [
        document.metadata.get("source", "")
        for document in caddy_response.get("context", [])
    ]
    ai_response_timestamp = datetime.now()
    response_card = chat_client.messages.generate_response_card(
        caddy_response["answer"]
    )
    llm_response = LlmResponse(
        message_id=caddy_event.message_id,
        llm_prompt=caddy_user_message.message,
        llm_answer=caddy_response["answer"],
        thread_id=caddy_user_message.message_id,
        llm_prompt_timestamp=ai_prompt_timestamp,
        llm_response_json=json.dumps(response_card),
        llm_response_timestamp=ai_response_timestamp,
        route=route or "no_route",
        context=context_sources,
    )
    store_response(llm_response)

    await chat_client.send_status_update(
        caddy_event, "supervisor_reviewing", status_activity_id
    )

    await chat_client.send_to_supervision(
        caddy_event, caddy_response["answer"], context_sources, status_activity_id
    )

    await chat_client.send_status_update(
        caddy_event, "awaiting_approval", status_activity_id
    )

    store_approver_received_timestamp(caddy_event)
