import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Tuple, Union

from boto3.dynamodb.conditions import Key
from caddy_core.models import (
    ApprovalEvent,
    CaddyMessageEvent,
    LlmResponse,
    UserMessage,
    LLMOutput,
    SupervisionEvent,
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
from langchain.prompts import PromptTemplate
from langchain_aws import ChatBedrock
import os

from langchain.output_parsers import PydanticOutputParser, RetryOutputParser
from pytz import timezone


class Caddy:
    def __init__(self, chat_client):
        self.chat_client = chat_client
        self.active_tasks = {}

    async def handle_message(self, caddy_message: CaddyMessageEvent):
        logger.debug(f"Running message handler for message: {caddy_message.message_id}")

        if caddy_message.message_id in self.active_tasks:
            logger.warning(
                f"Message {caddy_message.message_id} is already being processed"
            )
            return

        task = asyncio.create_task(self.process_message(caddy_message))
        self.active_tasks[caddy_message.message_id] = task
        try:
            await task
        finally:
            del self.active_tasks[caddy_message.message_id]

    async def process_message(self, caddy_message: CaddyMessageEvent):
        # module_values, survey_complete = self.check_existing_call(caddy_message)

        # if survey_complete:
        #     await self.chat_client.send_survey_complete_message(caddy_message)
        #     return

        # if not self.should_continue_conversation(module_values):
        #     await self.chat_client.send_control_group_message(
        #         caddy_message, module_values
        #     )
        #     return

        message_query = self.format_chat_message(caddy_message)
        self.store_message(message_query)

        status_message_id = await self.chat_client.send_status_update(
            message_query, "processing"
        )
        message_query.status_message_id = status_message_id

        try:
            is_follow_up = (
                False
                if "follow_up" in enrolment.get_features(message_query.user_email)
                else True
            )
            await self.send_to_llm(message_query, is_follow_up)
        except Exception as error:
            await self.handle_llm_error(message_query, error)

    async def send_to_llm(
        self,
        caddy_query: UserMessage,
        is_follow_up: bool = True,
        follow_up_context: str = "",
    ):
        try:
            status_message_id = await self.chat_client.send_status_update(
                caddy_query, "composing", caddy_query.status_message_id
            )
            caddy_query.status_message_id = status_message_id

            llm_output, context_sources = await self.get_llm_response(
                caddy_query, follow_up_context
            )

            await self.handle_llm_response(
                caddy_query, llm_output, context_sources, is_follow_up
            )

        except Exception as error:
            await self.handle_llm_error(caddy_query, error)

    async def get_llm_response(
        self,
        message_query: UserMessage,
        follow_up_context: str = "",
    ):
        chain, prompt = self.setup_llm_chain(message_query)

        reworded_query = self.reword_advisor_orchestration(
            message_query.message, follow_up_context
        )

        caddy_response = await chain.ainvoke(
            {
                "input": reworded_query,
                "chat_history": self.get_chat_history(message_query),
            }
        )

        context_sources = self.extract_context_sources(caddy_response)
        llm_output = self.parse_llm_output(caddy_response, prompt, reworded_query)

        return llm_output, context_sources

    def setup_llm_chain(self, message_query: UserMessage):
        query = message_query.message
        domain = (
            message_query.user_email.split("@")[1]
            if "@" in message_query.user_email
            else "unknown"
        )
        route_specific_augmentation, route = retrieve_route_specific_augmentation(query)
        day_date_time = datetime.now(timezone("Europe/London")).strftime(
            "%A %d %B %Y %H:%M"
        )
        _, office = enrolment.check_domain_status(domain)
        office_regions = enrolment.get_office_coverage(office)

        prompt = self.create_llm_prompt(
            route_specific_augmentation, day_date_time, office_regions
        )
        chain, _ = build_chain(prompt, user=message_query.user_email)
        return chain, prompt

    def create_llm_prompt(
        self, route_specific_augmentation, day_date_time, office_regions
    ):
        prompt_template = get_prompt("CORE_PROMPT")
        parser = PydanticOutputParser(pydantic_object=LLMOutput)
        prompt_template += (
            "\n{format_instructions}\n respond with json only - no other text"
        )
        return PromptTemplate(
            template=prompt_template,
            input_variables=["context", "input"],
            partial_variables={
                "route_specific_augmentation": route_specific_augmentation,
                "day_date_time": day_date_time,
                "office_regions": ", ".join(office_regions),
                "format_instructions": parser.get_format_instructions(),
            },
        )

    def extract_context_sources(self, caddy_response):
        return [
            document.metadata.get("source", "")
            for document in caddy_response.get("context", [])
        ]

    def parse_llm_output(self, caddy_response, prompt, reworded_query):
        parser = PydanticOutputParser(pydantic_object=LLMOutput)
        retry_parser = RetryOutputParser.from_llm(
            parser=parser,
            llm=ChatBedrock(
                model_id=os.getenv("AGENT_LLM"),
                region_name="eu-west-3",
                model_kwargs={"temperature": 0, "top_k": 5},
            ),
        )
        prompt_value = prompt.format_prompt(
            context=caddy_response.get("context", []), input=reworded_query
        )
        llm_output = retry_parser.parse_with_prompt(
            caddy_response["answer"], prompt_value
        )
        _, llm_output.message = self.remove_role_played_responses(llm_output.message)
        return llm_output

    async def handle_llm_response(
        self,
        message_query: UserMessage,
        llm_output: LLMOutput,
        context_sources: List[str],
        is_follow_up: bool = True,
    ):
        """
        Handle LLM response
        """

        if llm_output.follow_up_questions and not is_follow_up:
            await self.chat_client.send_follow_up_questions(
                message_query,
                llm_output,
                context_sources,
                message_query.status_message_id,
            )
            return

        response_card = self.chat_client.create_card(
            llm_output.message, context_sources
        )

        llm_response = self.create_llm_response(
            message_query, llm_output, response_card, context_sources
        )

        supervision_event = self.create_supervision_event(message_query, llm_response)

        status_message_id = await self.chat_client.send_status_update(
            message_query, "supervisor_reviewing", message_query.status_message_id
        )
        message_query.status_message_id = status_message_id

        (
            supervision_message_id,
            supervisor_thread_id,
        ) = await self.chat_client.send_supervision_request(
            message_query, supervision_event, response_card
        )

        llm_response.supervision_message_id = supervision_message_id
        llm_response.supervisor_thread_id = supervisor_thread_id
        self.store_response(llm_response)

        await self.chat_client.send_status_update(
            message_query, "awaiting_approval", message_query.status_message_id
        )

    async def handle_llm_error(
        self,
        message_query: UserMessage,
        error: Exception,
    ):
        """
        Handle LLM errors
        """

        logger.error(f"Error in send_to_llm: {str(error)}")

        supervisor_space = enrolment.get_designated_supervisor_space(
            message_query.user_email
        )

        if hasattr(message_query, "supervision_message_id"):
            await self.chat_client.update_supervision_status(
                space_id=supervisor_space,
                thread_id=message_query.thread_id,
                message_id=message_query.supervision_message_id,
                status="failed",
                user=message_query.user_email,
                query=message_query.message,
            )

        await self.chat_client.send_status_update(
            message_query, "request_failure", message_query.status_message_id
        )

        raise Exception(f"Caddy response failed: {error}")

    def check_existing_call(
        self, caddy_message: CaddyMessageEvent
    ) -> Tuple[Dict[str, Any], bool]:
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
                    "continueConversation": response["Items"][0][
                        "continueConversation"
                    ],
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
        self.store_evaluation_module(
            user=caddy_message.user,
            thread_id=caddy_message.thread_id,
            module_values=module_values,
        )
        return module_values, survey_complete

    def should_continue_conversation(self, module_values):
        return module_values["continueConversation"]

    def store_evaluation_module(self, user, thread_id, module_values):
        user_arguments = module_values["modulesUsed"][0]
        argument_output = module_values["moduleOutputs"]
        continue_conversation = module_values["continueConversation"]
        control_group_message = module_values["controlGroupMessage"]
        user_arguments["module_arguments"]["split"] = str(
            user_arguments["module_arguments"]["split"]
        )
        call_start_time = datetime.now().strftime("%d-%m-%Y %H:%M")
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

    def format_chat_message(self, event: CaddyMessageEvent) -> UserMessage:
        return UserMessage(
            conversation_id=event.space_id,
            thread_id=event.thread_id,
            message_id=event.message_id,
            client=event.source_client,
            user_email=event.user,
            message=event.message_string,
            message_sent_timestamp=str(event.timestamp),
            message_received_timestamp=datetime.now(),
            teams_conversation=event.teams_conversation,
            teams_from=event.teams_from,
            teams_recipient=event.teams_recipient,
        )

    def store_message(self, message: UserMessage):
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

    def store_response(self, response: LlmResponse):
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

    def store_user_thanked_timestamp(
        self, ai_answer: Union[LlmResponse, SupervisionEvent]
    ):
        responses_table.update_item(
            Key={"threadId": ai_answer.thread_id},
            UpdateExpression="set userThankedTimestamp=:t",
            ExpressionAttributeValues={":t": str(datetime.now())},
            ReturnValues="UPDATED_NEW",
        )

    def store_approver_received_timestamp(
        self,
        event: Union[SupervisionEvent, CaddyMessageEvent],
    ):
        thread_id = event.thread_id if hasattr(event, "thread_id") else event.message_id
        responses_table.update_item(
            Key={"threadId": str(thread_id)},
            UpdateExpression="set approverReceivedTimestamp=:t",
            ExpressionAttributeValues={":t": str(datetime.now())},
            ReturnValues="UPDATED_NEW",
        )

    def store_approver_event(self, thread_id: str, approval_event: ApprovalEvent):
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

    def get_chat_history(self, message: UserMessage) -> List:
        response = responses_table.query(
            KeyConditionExpression=Key("threadId").eq(message.thread_id),
        )

        sorted_items = sorted(
            response["Items"],
            key=lambda x: x.get(
                "messageReceivedTimestamp", x.get("llmPromptTimestamp", "")
            ),
        )

        return self.format_chat_history(sorted_items)

    def format_chat_history(self, user_messages: List) -> List:
        history_langchain_format = []
        for message in user_messages:
            human = message.get("llmPrompt")
            ai = message.get("llmAnswer")

            if human and ai:
                history_langchain_format.append((human, ai))
            elif human:
                history_langchain_format.append((human, ""))

        return history_langchain_format

    def remove_role_played_responses(self, response: str) -> Tuple[bool, str]:
        adviser_index = response.find("Adviser: ")
        if adviser_index != -1:
            logger.debug("Removing role played response")
            return True, response[:adviser_index].strip()

        adviser_index = response.find("Advisor: ")
        if adviser_index != -1:
            logger.debug("Removing role played response")
            return True, response[:adviser_index].strip()

        return False, response.strip()

    def reword_advisor_orchestration(
        self, original_query: str, follow_up_context: str = ""
    ) -> str:
        combined_input = f"Original Query: {original_query}\n\nAdditional Context: {follow_up_context}"
        reworded_query = self.reword_advisor_message(combined_input)

        if 50 <= len(reworded_query) <= 200:
            return reworded_query

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

        # logger.debug(f"content: {content}")

        return content

    def reword_advisor_message(self, message: str) -> str:
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

        # logger.debug(f"reworded query: {response}")

        return response.content

    def create_llm_response(
        self,
        message_query: UserMessage,
        llm_output: LLMOutput,
        response_card: Dict,
        context_sources: List[str],
    ):
        return LlmResponse(
            message_id=message_query.message_id,
            llm_prompt=message_query.message,
            llm_answer=llm_output.message,
            thread_id=message_query.thread_id,
            llm_prompt_timestamp=datetime.now(),
            llm_response_json=json.dumps(response_card),
            llm_response_timestamp=datetime.now(),
            route=retrieve_route_specific_augmentation(message_query.message)[1]
            or "no_route",
            context=context_sources,
        )

    def create_supervision_event(
        self, message_query: UserMessage, llm_response: LlmResponse
    ):
        return SupervisionEvent(
            type="SUPERVISION_REQUIRED",
            source_client=message_query.client,
            user=message_query.user_email,
            llmPrompt=llm_response.llm_prompt,
            llm_answer=llm_response.llm_answer,
            llm_response_json=json.dumps(llm_response.llm_response_json),
            conversation_id=message_query.conversation_id,
            thread_id=message_query.thread_id,
            message_id=message_query.message_id,
            response_id=str(llm_response.response_id),
            status_message_id=message_query.status_message_id,
        )

    async def process_follow_up_answers(
        self, message_query: UserMessage, follow_up_context: str
    ):
        try:
            await self.chat_client.send_status_update(
                message_query, "composing", message_query.status_message_id
            )

            task = asyncio.create_task(
                self.send_to_llm(
                    message_query,
                    is_follow_up=True,
                    follow_up_context=follow_up_context,
                )
            )
            self.active_tasks[message_query.message_id] = task
            try:
                await task
            finally:
                del self.active_tasks[message_query.message_id]
        except Exception as error:
            await self.handle_llm_error(message_query, error)

    @staticmethod
    def mark_call_complete(user: str, thread_id: str) -> None:
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

    def _create_client_friendly_prompt(self, content: Dict[str, Any]) -> str:
        """
        Create prompt for client friendly response
        """
        return f"""
        You are an AI assistant tasked with converting a technical response into a client-friendly letter style version
        to be returned to the client via email as an overview to their advice session. Your task is to:

        1. Simplify the language, avoiding jargon and technical terms.
        2. Summarise the key points in a way that's easy for the client to understand.
        3. Maintain the essential information and advice, but present it in a more conversational tone.
        4. Exclude any internal references (such as advisernet) or notes that aren't relevant to the client.
        5. Keep your response concise, aiming for about half the length of the original content.

        Keep the style in line with "as discussed in our recent contact these are available options" do not
        include any follow up questions for the client but phrase as paths they can explore. This is after
        contact so do not ask if any further support is required, instead let the client know they can get
        contact the service if they need further help in the future.

        Include any public facing helpful links at the end of the response.

        Here's the content to convert:

        {content}

        Please provide the client-friendly version:
        """

    async def create_client_friendly(
        self, card_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert response to client friendly format
        """
        llm = ChatBedrock(
            model_id=os.getenv("LLM"),
            region_name="eu-west-3",
            model_kwargs={"temperature": 0.3, "top_k": 5, "max_tokens": 2000},
        )

        prompt = self._create_client_friendly_prompt(card_content)
        response = llm.invoke(prompt)

        return response.content
