import os
import json
import re
import asyncio
import requests
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from caddy_core.models import (
    ChatIntegration,
    CaddyMessageEvent,
    UserNotEnrolledException,
    ApprovalEvent,
    UserMessage,
    LLMOutput,
    SupervisionEvent,
)
from caddy_core.services import enrolment
from caddy_core.utils.monitoring import logger
from caddy_core.components import Caddy
from caddy_core.services.anonymise import analyse
from caddy_core.services.survey import get_survey, check_if_survey_required
from integrations.google_chat import content, responses
from googleapiclient.discovery import build
from integrations.google_chat.auth import get_google_creds

from urllib.parse import urlparse, urlunparse

from thefuzz import fuzz


class GoogleChat(ChatIntegration):
    def __init__(self):
        self.client = "Google Chat"
        self.messages = content
        self.responses = responses
        self.caddy = build(
            "chat",
            "v1",
            credentials=get_google_creds(os.getenv("CADDY_SERVICE_ACCOUNT")),
        )
        self.supervisor = build(
            "chat",
            "v1",
            credentials=get_google_creds(os.getenv("CADDY_SUPERVISOR_SERVICE_ACCOUNT")),
        )
        self.caddy_instance = Caddy(self)
        self.active_tasks = {}

    def _extract_status_message_id(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract the status message ID from the event or card content.
        """
        if "statusMessageId" in event.get("common", {}).get("parameters", {}):
            return event["common"]["parameters"]["statusMessageId"]

        if "message" in event and "cardsV2" in event["message"]:
            return event["message"]["name"].split("/")[3]

        return None

    async def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for handling Google Chat events
        """
        user = event["user"]["email"]
        domain = user.split("@")[1]

        domain_enrolled, office = enrolment.check_domain_status(domain)
        if not domain_enrolled:
            logger.info("Domain not enrolled")
            return self.responses.DOMAIN_NOT_ENROLLED

        user_enrolled, user_record = enrolment.check_user_status(user)
        if not user_enrolled:
            logger.info("User is not enrolled")
            return self.responses.USER_NOT_ENROLLED

        event_type = event.get("type")
        match event_type:
            case "ADDED_TO_SPACE":
                return await self.handle_added_to_space(event)
            case "MESSAGE":
                return await self.handle_message(event, user_record, office)
            case "CARD_CLICKED":
                return await self.handle_card_clicked(event)
            case _:
                logger.warning(f"Unhandled event type: {event_type}")
                return self.responses.NO_CONTENT

    async def handle_added_to_space(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle when Caddy is added to a space
        """
        match event["space"]["type"]:
            case "DM":
                return self.responses.INTRODUCE_CADDY_IN_DM
            case "ROOM":
                return self.responses.introduce_caddy_in_space(
                    space_name=event["space"]["displayName"]
                )

    async def handle_message(
        self, event: Dict[str, Any], user_record: Dict[str, Any], office: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle incoming messages
        """
        included_in_rct = enrolment.check_rct_status(office)
        if included_in_rct and await self.check_existing_call(event, user_record):
            return self.responses.NO_CONTENT

        caddy_message = await self.format_event_to_message(event)
        if caddy_message == "PII Detected":
            return self.responses.NO_CONTENT

        if caddy_message.message_id not in self.active_tasks:
            task = asyncio.create_task(
                self.caddy_instance.process_message(caddy_message)
            )
            self.active_tasks[caddy_message.message_id] = task
            task.add_done_callback(
                lambda t: self.remove_active_task(caddy_message.message_id)
            )

        return self.responses.ACCEPTED

    def remove_active_task(self, message_id: str) -> None:
        """
        Remove task from active tasks
        """
        self.active_tasks.pop(message_id, None)

    async def handle_card_clicked(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle card click events
        """
        action_name = event["action"]["actionMethodName"]
        match action_name:
            case "Proceed":
                return await self.handle_proceed_query(event)
            case "handle_control_group_forward":
                return await self.handle_control_group_forward(event)
            case "edit_query_dialog":
                return await self.get_edit_query_dialog(event)
            case "receiveEditedQuery":
                return await self.handle_edited_query(event)
            case "continue_existing_interaction":
                return await self.continue_existing_interaction(event)
            case "end_existing_interaction":
                return await self.end_existing_interaction(event)
            case "survey_response":
                return await self.handle_survey_response(event)
            case "call_complete":
                return await self.finalise_caddy_call(event)
            case "convert_to_client_friendly":
                return await self.convert_to_client_friendly(event)
            case "handle_follow_up_answers":
                return await self.process_follow_up_answers(event)
            case _:
                logger.warning(f"Unhandled card action: {action_name}")
                return self.responses.NO_CONTENT

    async def handle_supervision_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle supervision events
        """
        user = event["user"]["email"]
        user_enrolled, user_record = enrolment.check_user_status(user)
        if not user_enrolled:
            raise UserNotEnrolledException("User is not enrolled in Caddy.")

        user_supervisor = enrolment.check_user_role(user_record)
        if not user_supervisor:
            return self.responses.USER_NOT_SUPERVISOR

        event_type = event.get("type")
        match event_type:
            case "ADDED_TO_SPACE":
                return await self.handle_supervisor_added_to_space(event)
            case "CARD_CLICKED":
                return await self.handle_supervisor_card_clicked(event)
            case "MESSAGE":
                return await self.handle_supervisor_message(event)
            case _:
                logger.warning(f"Unhandled supervision event type: {event_type}")
                return self.responses.NO_CONTENT

    async def handle_supervisor_added_to_space(
        self, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle when Caddy Supervisor is added to a space
        """
        match event["space"]["type"]:
            case "DM":
                return self.responses.INTRODUCE_CADDY_SUPERVISOR_IN_DM
            case "ROOM":
                return self.responses.introduce_caddy_supervisor_in_space(
                    space_name=event["space"]["displayName"]
                )

    async def handle_supervisor_card_clicked(
        self, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle supervisor card click events
        """
        try:
            action_name = event["action"]["actionMethodName"]
            match action_name:
                case "Approved":
                    approval_event, response_card = self._create_approval_event(event)
                    return await self.handle_supervision_approval(
                        event=event,
                        approval_event=approval_event,
                        response_card=response_card,
                    )
                case "Rejected":
                    rejection_event = self._create_rejection_event(event)
                    return await self.handle_supervision_rejection(
                        event=event, rejection_event=rejection_event
                    )
                case "receiveDialog":
                    return await self.handle_supervisor_dialog(event)
                case _:
                    logger.warning(f"Unhandled supervisor card action: {action_name}")
                    return self.responses.NO_CONTENT
        except Exception as e:
            logger.error(f"Error processing supervisor card click: {str(e)}")
            return self.responses.NO_CONTENT

    async def handle_supervisor_message(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle supervisor message events
        """
        if event["dialogEventType"] == "REQUEST_DIALOG":
            match event["message"]["annotations"][0]["slashCommand"]["commandName"]:
                case "/addUser":
                    return self.responses.ADD_USER_DIALOG
                case "/removeUser":
                    return self.responses.REMOVE_USER_DIALOG
                case "/help":
                    return self.responses.HELPER_DIALOG
                case "/listUsers":
                    return await self.list_users(event)
        return self.responses.NO_CONTENT

    async def check_existing_call(
        self, event: Dict[str, Any], user_record: Dict[str, Any]
    ) -> bool:
        """
        Check if there's an existing call and send a reminder if necessary
        """
        user_has_existing_call = enrolment.check_user_call_status(user_record)
        if user_has_existing_call and event["type"] == "MESSAGE":
            space_id = event["space"]["name"].split("/")[1]
            thread_id = (
                event["message"]["thread"]["name"].split("/")[3]
                if "thread" in event["message"]
                else None
            )

            await self._send_existing_call_reminder(
                space_id=space_id,
                thread_id=thread_id,
                call_start_time=user_record["callStart"],
                survey_thread_id=user_record["activeThreadId"],
                event=event,
            )
            return True
        return False

    async def format_event_to_message(self, event: Dict[str, Any]) -> CaddyMessageEvent:
        """
        Convert Google Chat event to CaddyMessageEvent
        """
        space_id = event["space"]["name"].split("/")[1]
        thread_id = (
            event["message"]["thread"]["name"].split("/")[3]
            if "thread" in event["message"]
            else None
        )
        message_string = event["message"]["text"].replace("@Caddy", "").strip()

        # Check for PII
        if "proceed" not in event:
            pii_identified = analyse(message_string)
            if pii_identified:
                # Optionally redact PII from the message by importing redact from services.anonymise
                # message_string = redact(message_string, pii_identified)

                await self.send_pii_warning(space_id, thread_id, message_string, event)
                return "PII Detected"

        return CaddyMessageEvent(
            type="PROCESS_CHAT_MESSAGE",
            user=event["user"]["email"],
            name=event["user"]["name"],
            space_id=space_id,
            thread_id=thread_id,
            message_id=event["message"]["name"].split("/")[3],
            message_string=message_string,
            source_client=self.client,
            timestamp=event["eventTime"],
        )

    async def _send_existing_call_reminder(
        self,
        space_id: str,
        thread_id: str,
        call_start_time: str,
        survey_thread_id: str,
        event: Dict[str, Any],
    ) -> None:
        """
        Send a reminder for an existing call
        """
        reminder_card = self.responses.existing_call_reminder(
            event, space_id, thread_id, call_start_time, survey_thread_id
        )
        await self.send_message(space_id, reminder_card)

    async def send_pii_warning(
        self,
        space_id: str,
        thread_id: str,
        message: str,
        original_event: Dict[str, Any],
    ) -> None:
        """
        Send a PII warning to the adviser space
        """
        warning_card = self.create_pii_warning(message, original_event)

        if thread_id:
            warning_card["thread"] = {"name": f"spaces/{space_id}/threads/{thread_id}"}

        await self.send_message(space_id, warning_card)

    def create_pii_warning(
        self, message: str, original_event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create PII Warning Card for Google Chat
        """
        return self.responses.create_pii_warning_card(message, original_event)

    async def handle_proceed_query(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a proceed query event
        """
        event = json.loads(event["common"]["parameters"]["message_event"])
        event["proceed"] = True
        caddy_message = await self.format_event_to_message(event)
        await self.caddy_instance.handle_message(caddy_message)
        return self.responses.ACCEPTED

    async def get_edit_query_dialog(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the edit query dialog
        """
        message_string = (
            event["common"]["parameters"]["original_message"]
            .replace("@Caddy", "")
            .strip()
        )
        edit_query_dialog = self.responses.edit_query_dialog(event, message_string)
        return edit_query_dialog

    async def handle_edited_query(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an edited query event
        """
        edited_message = event["common"]["formInputs"]["editedQuery"]["stringInputs"][
            "value"
        ][0]
        event = json.loads(event["common"]["parameters"]["message_event"])
        event["message"]["text"] = edited_message
        event["proceed"] = True
        caddy_message = await self.format_event_to_message(event)
        await self.caddy_instance.handle_message(caddy_message)
        return self.responses.ACCEPTED

    async def handle_control_group_forward(
        self, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle a control group forward event
        """
        message_event = event["common"]["parameters"]["message_event"]
        caddy_message_event = json.loads(message_event)
        caddy_message = CaddyMessageEvent(**caddy_message_event)

        supervisor_space = enrolment.get_designated_supervisor_space(caddy_message.user)
        await self.send_message_to_supervision_space(
            space_id=supervisor_space,
            message=self.responses.message_control_forward(
                caddy_message.user, caddy_message.message_string
            ),
        )

        control_group_card = event["message"]["cardsV2"]
        control_group_card[0]["card"]["sections"][0]["widgets"].pop()
        control_group_card[0]["card"]["sections"][0]["widgets"].append(
            {
                "textParagraph": {
                    "text": '<font color="#005743"><b>Request forwarded to supervisor<b></font>'
                }
            }
        )
        control_group_card = self.append_survey_questions(
            control_group_card, caddy_message.thread_id, caddy_message.user
        )
        await self.update_message(
            space_id=caddy_message.space_id,
            message_id=caddy_message.message_id,
            message={"cardsV2": control_group_card},
        )
        return self.responses.NO_CONTENT

    async def send_message(
        self, space_id: str, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a message to a Google Chat space
        """
        try:
            response = (
                self.caddy.spaces()
                .messages()
                .create(
                    parent=f"spaces/{space_id}",
                    body=message,
                )
                .execute()
            )
            return response
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            raise

    async def update_message(
        self, space_id: str, message_id: str, message: Dict[str, Any]
    ) -> None:
        """
        Update an existing message
        """
        try:
            self.caddy.spaces().messages().patch(
                name=f"spaces/{space_id}/messages/{message_id}",
                body=message,
                updateMask="cardsV2",
            ).execute()
        except Exception as e:
            logger.error(f"Error updating message: {str(e)}")
            raise

    async def send_status_update(
        self, message: UserMessage, status: str, message_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Send or update a status message
        """
        status_cards = {
            "processing": self.messages.PROCESSING_MESSAGE,
            "composing": self.messages.COMPOSING_MESSAGE,
            "composing_retry": self.messages.COMPOSING_MESSAGE_RETRY,
            "request_failure": self.messages.REQUEST_FAILURE,
            "supervisor_reviewing": self.messages.SUPERVISOR_REVIEWING_RESPONSE,
            "awaiting_approval": self.messages.AWAITING_SUPERVISOR_APPROVAL,
        }

        if status not in status_cards:
            logger.error(f"Unknown status: {status}")
            return None

        status_card = status_cards[status]

        try:
            if message_id:
                await self.update_message(
                    space_id=message.conversation_id,
                    message_id=message_id,
                    message=status_card,
                )
                return message_id
            else:
                if hasattr(message, "thread_id") and message.thread_id:
                    status_card["thread"] = {
                        "name": f"spaces/{message.conversation_id}/threads/{message.thread_id}"
                    }

                response = await self.send_message(
                    space_id=message.conversation_id, message=status_card
                )
                return response.get("name", "").split("/")[-1]
        except Exception as e:
            logger.error(f"Error sending status update: {str(e)}")
            return None

    async def update_message_in_supervision_space(
        self, space_id: str, message_id: str, message: Dict[str, Any]
    ) -> None:
        """
        Update an existing message in the supervision space
        """
        try:
            self.supervisor.spaces().messages().patch(
                name=f"spaces/{space_id}/messages/{message_id}",
                body=message,
                updateMask="cardsV2",
            ).execute()
        except Exception as e:
            logger.error(f"Error updating message in supervision space: {str(e)}")
            raise

    async def send_message_to_supervision_space(
        self, space_id: str, message: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Send message to supervision space and return thread and message IDs
        """
        try:
            response = (
                self.supervisor.spaces()
                .messages()
                .create(parent=f"spaces/{space_id}", body=message)
                .execute()
            )

            thread_id = (
                response["thread"]["name"].split("/")[3]
                if "thread" in response
                else response["name"].split("/")[3]
            )
            message_id = response["name"].split("/")[3]

            return thread_id, message_id
        except Exception as e:
            logger.error(f"Error sending message to supervision space: {str(e)}")
            raise

    def create_card(
        self, llm_output: str, context_sources: List[str]
    ) -> Dict[str, Any]:
        """
        Create Google Chat card from LLM response
        """
        card = {
            "cardsV2": [
                {
                    "cardId": "aiResponseCard",
                    "card": {
                        "sections": [],
                    },
                }
            ]
        }

        url_matches = re.findall(
            r"<ref>((?:SOURCE_URL:)?(http[s]?://[^\s>]+))</ref>", llm_output
        )
        processed_urls = []
        ref_count = 0
        reference_section = {"header": "Reference links", "widgets": []}

        for full_url, base_url in url_matches:
            if full_url in processed_urls:
                continue

            url_to_check = full_url.replace("SOURCE_URL:", "")
            url_parts = urlparse(url_to_check)
            base_url = urlunparse(url_parts._replace(fragment=""))
            fragment = url_parts.fragment

            best_match = max(context_sources, key=lambda x: fuzz.ratio(base_url, x))
            match_score = fuzz.ratio(base_url, best_match)
            use_url = best_match if match_score > 95 else base_url

            url_valid = self._validate_url(use_url, context_sources)
            if url_valid:
                ref_count += 1
                domain = self._get_domain(use_url)
                full_use_url = f"{use_url}#{fragment}" if fragment else use_url

                llm_output = llm_output.replace(
                    f"<ref>{full_url}</ref>",
                    f'<a href="{full_use_url}">[{ref_count} - {domain}]</a>',
                )

                reference_section["widgets"].append(
                    {
                        "textParagraph": {
                            "text": f'<a href="{full_use_url}">[{ref_count} - {domain}] {full_use_url}</a>'
                        }
                    }
                )

                processed_urls.append(full_url)
            else:
                llm_output = llm_output.replace(f"<ref>{full_url}</ref>", "")

        card["cardsV2"][0]["card"]["sections"].append(
            {
                "widgets": [
                    {"textParagraph": {"text": llm_output}},
                ],
            }
        )

        if reference_section["widgets"]:
            card["cardsV2"][0]["card"]["sections"].append(reference_section)

        return card

    async def send_supervision_request(
        self,
        message_query: UserMessage,
        supervision_event: SupervisionEvent,
        response_card: Dict[str, Any],
    ) -> Tuple[str, str]:
        """
        Send request to supervision space
        """
        supervisor_space = enrolment.get_designated_supervisor_space(
            message_query.user_email
        )

        status_card = self.responses.supervisor_request_pending(
            supervision_event.user, supervision_event.llmPrompt
        )

        (
            supervision_thread_id,
            supervision_message_id,
        ) = await self.send_message_to_supervision_space(
            space_id=supervisor_space, message=status_card
        )

        supervision_card = self.responses.create_supervision_card(
            user_email=supervision_event.user,
            event=supervision_event,
            new_request_message_id=supervision_message_id,
            request_approved=self.responses.supervisor_request_approved(
                supervision_event.user, supervision_event.llmPrompt
            ),
            request_rejected=self.responses.supervisor_request_rejected(
                supervision_event.user, supervision_event.llmPrompt
            ),
            card_for_approval=response_card,
        )

        supervision_message = {
            "cardsV2": supervision_card["cardsV2"],
            "thread": {
                "name": f"spaces/{supervisor_space}/threads/{supervision_thread_id}"
            },
        }

        try:
            self.supervisor.spaces().messages().create(
                parent=f"spaces/{supervisor_space}",
                messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
                body=supervision_message,
            ).execute()
        except Exception as e:
            logger.error(f"Error sending threaded supervision message: {str(e)}")
            raise

        self.caddy_instance.store_approver_received_timestamp(supervision_event)

        return supervision_message_id, supervision_thread_id

    async def update_supervision_status(
        self, space_id: str, message_id: str, status: str, user: str, query: str
    ) -> None:
        """
        Update supervisor message with current status..
        """

        status_cards = {
            "processing": self.responses.supervisor_request_processing,
            "awaiting": self.responses.supervisor_request_pending,
            "failed": self.responses.supervisor_request_failed,
            "approved": self.responses.supervisor_request_approved,
            "rejected": self.responses.supervisor_request_rejected,
        }

        if status not in status_cards:
            logger.error(f"Unknown supervisor status: {status}")
            return

        status_card = status_cards[status](user, query)

        await self.update_message_in_supervision_space(
            space_id=space_id, message_id=message_id, message=status_card
        )

    async def handle_supervision_approval(
        self,
        event: Dict[str, Any],
        approval_event: ApprovalEvent,
        response_card: Dict[str, Any],
    ) -> None:
        """
        Handle supervision approval flow
        """
        try:
            user = event["common"]["parameters"]["userEmail"]
            user_space = event["common"]["parameters"]["conversationId"]
            supervisor_message_id = event["message"]["name"].split("/")[3]
            thread_id = event["common"]["parameters"]["threadId"]
            original_query = event["common"]["parameters"]["original_query"]

            supervisor_space = event["space"]["name"].split("/")[1]
            status_message_id = event["common"]["parameters"]["newRequestId"]

            status_card = self.responses.supervisor_request_approved(
                user, original_query
            )

            try:
                await self.update_message_in_supervision_space(
                    space_id=supervisor_space,
                    message_id=status_message_id,
                    message=status_card,
                )
            except Exception as e:
                logger.error(f"Error updating supervisor status: {str(e)}")
                raise

            approval_section = self.responses.approval_json_widget(
                approver=approval_event.approver_email,
                supervisor_notes=approval_event.supervisor_message,
            )

            card_sections = []
            for section in response_card["cardsV2"][0]["card"]["sections"]:
                if not any(
                    w.get("buttonList") or w.get("textInput")
                    for w in section.get("widgets", [])
                ):
                    card_sections.append(section)

            updated_card = {
                "cardsV2": [
                    {
                        "cardId": response_card["cardsV2"][0]["cardId"],
                        "card": {"sections": [approval_section] + card_sections},
                    }
                ]
            }

            try:
                self.supervisor.spaces().messages().patch(
                    name=f"spaces/{supervisor_space}/messages/{supervisor_message_id}",
                    updateMask="cardsV2",
                    body=updated_card,
                ).execute()
            except Exception as e:
                logger.error(f"Error updating supervisor message: {str(e)}")
                raise

            adviser_card = self.responses.create_client_friendly_card(updated_card)

            try:
                await self.update_message(
                    space_id=user_space,
                    message_id=event["common"]["parameters"]["status_id"],
                    message=adviser_card,
                )
            except Exception as e:
                logger.error(f"Error updating adviser message: {str(e)}")
                raise

            self.caddy_instance.store_approver_event(thread_id, approval_event)

        except Exception as e:
            logger.error(f"Error in handle_supervision_approval: {str(e)}")
            raise

    async def handle_supervision_rejection(
        self, event: Dict[str, Any], rejection_event: ApprovalEvent
    ) -> None:
        """
        Handle supervision rejection flow
        """
        try:
            user = event["common"]["parameters"]["userEmail"]
            user_space = event["common"]["parameters"]["conversationId"]
            supervisor_message_id = event["message"]["name"].split("/")[3]
            thread_id = event["common"]["parameters"]["threadId"]
            original_query = event["common"]["parameters"]["original_query"]

            supervisor_space = event["space"]["name"].split("/")[1]
            status_message_id = event["common"]["parameters"]["newRequestId"]

            status_card = self.responses.supervisor_request_rejected(
                user, original_query
            )
            try:
                await self.update_message_in_supervision_space(
                    space_id=supervisor_space,
                    message_id=status_message_id,
                    message=status_card,
                )
            except Exception as e:
                logger.error(f"Error updating supervisor status: {str(e)}")
                raise

            rejection_section = self.responses.rejection_json_widget(
                approver=rejection_event.approver_email,
                supervisor_message=rejection_event.supervisor_message,
            )

            card_sections = []
            ai_response = json.loads(event["common"]["parameters"]["aiResponse"])
            for section in ai_response["cardsV2"][0]["card"]["sections"]:
                if not any(
                    w.get("buttonList") or w.get("textInput")
                    for w in section.get("widgets", [])
                ):
                    card_sections.append(section)

            supervisor_card = {
                "cardsV2": [
                    {
                        "cardId": f"rejectionCard_{thread_id}",
                        "card": {"sections": [rejection_section] + card_sections},
                    }
                ]
            }

            try:
                self.supervisor.spaces().messages().patch(
                    name=f"spaces/{supervisor_space}/messages/{supervisor_message_id}",
                    updateMask="cardsV2",
                    body=supervisor_card,
                ).execute()
            except Exception as e:
                logger.error(f"Error updating supervisor message: {str(e)}")
                raise

            adviser_card = self.responses.supervisor_rejection(
                approver=rejection_event.approver_email,
                supervisor_message=rejection_event.supervisor_message,
            )

            try:
                await self.update_message(
                    space_id=user_space,
                    message_id=event["common"]["parameters"]["status_id"],
                    message=adviser_card,
                )
            except Exception as e:
                logger.error(f"Error updating adviser message: {str(e)}")
                raise

            self.caddy_instance.store_approver_event(thread_id, rejection_event)

        except Exception as e:
            logger.error(f"Error in handle_supervision_rejection: {str(e)}")
            raise

    async def send_follow_up_questions(
        self,
        message_query: UserMessage,
        llm_output: LLMOutput,
        context_sources: List[str],
        status_message_id: Optional[str] = None,
    ) -> None:
        """
        Send follow-up questions to user
        """
        follow_up_card = self.responses.create_follow_up_questions_card(
            llm_output, message_query
        )

        if status_message_id:
            await self.update_message(
                space_id=message_query.conversation_id,
                message_id=status_message_id,
                message=follow_up_card,
            )
        else:
            await self.send_message(
                space_id=message_query.conversation_id,
                message=follow_up_card,
            )

    async def process_follow_up_answers(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process follow-up answers from user
        """
        original_query = event["common"]["parameters"]["original_query"]
        original_message = event["common"]["parameters"]["original_message"]
        follow_up_questions = json.loads(
            event["common"]["parameters"]["follow_up_questions"]
        )
        status_message_id = self._extract_status_message_id(event)

        follow_up_context = self._build_follow_up_context(
            original_query, original_message, follow_up_questions, event
        )

        message_query = UserMessage(
            conversation_id=event["space"]["name"].split("/")[1],
            thread_id=event["common"]["parameters"]["original_thread_id"],
            message_id=event["message"]["name"].split("/")[3],
            client=self.client,
            user_email=event["user"]["email"],
            message=original_query,
            message_sent_timestamp=str(datetime.now()),
            message_received_timestamp=datetime.now(),
            status_message_id=status_message_id,
        )

        await self.caddy_instance.process_follow_up_answers(
            message_query, follow_up_context
        )

        return self.responses.ACCEPTED

    async def send_survey(self, user: str, thread_id: str, space_id: str) -> None:
        """
        Send survey to user
        """
        survey_card = self._create_survey_card(user, thread_id)
        await self.send_dynamic_to_adviser_space(
            response_type="cardsV2",
            space_id=space_id,
            message=survey_card,
            thread_id=thread_id,
        )

    async def handle_survey_response(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle survey response
        """
        user = event["user"]["email"]
        thread_id = event["common"]["parameters"]["threadId"]
        space_id = event["space"]["name"].split("/")[1]
        message_id = event["message"]["name"].split("/")[3]
        message_event = event["common"]["parameters"]["event"]

        questions_and_values = []
        for question, response in event["common"]["formInputs"].items():
            value = response["stringInputs"]["value"][0]
            questions_and_values.append({question: value})

        self.caddy_instance.store_survey_response(thread_id, questions_and_values)

        card = event["message"]["cardsV2"]
        card[0]["card"]["sections"].pop()
        if message_event:
            card[0]["card"]["sections"].pop()
        card[0]["card"]["sections"].append(self.messages.SURVEY_COMPLETE_WIDGET)

        self.caddy_instance.mark_call_complete(user=user, thread_id=thread_id)

        await self.update_survey_card_in_adviser_space(
            space_id=space_id, message_id=message_id, card={"cardsV2": card}
        )

        return message_event if message_event else self.responses.NO_CONTENT

    async def create_supervision_card(
        self,
        user_email: str,
        supervision_event: SupervisionEvent,
        response_card: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create supervision card for review
        """
        return self.responses.create_supervision_card(
            user_email=user_email,
            event=supervision_event,
            new_request_message_id=None,
            request_approved=self.responses.supervisor_request_approved(
                user_email, supervision_event.llmPrompt
            ),
            request_rejected=self.responses.supervisor_request_rejected(
                user_email, supervision_event.llmPrompt
            ),
            card_for_approval=response_card,
        )

    async def convert_to_client_friendly(
        self, card_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert response to client friendly format
        """
        response = await self.caddy_instance.create_client_friendly(card_content)

        return self.responses.create_client_friendly_dialog(response)

    async def add_user(self, event: Dict[str, Any]) -> None:
        """
        Add user to Caddy
        """
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]
        role = event["common"]["formInputs"]["role"]["stringInputs"]["value"][0]
        supervisor_space_id = event["space"]["name"].split("/")[1]

        try:
            enrolment.register_user(user, role, supervisor_space_id)
        except Exception as error:
            logger.error(f"Adding user failed: {error}")

    async def remove_user(self, event: Dict[str, Any]) -> None:
        """
        Remove user from Caddy
        """
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]
        try:
            enrolment.remove_user(user)
        except Exception as error:
            logger.error(f"Removing user failed: {error}")

    async def list_users(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        List users in space
        """
        space_id = event["space"]["name"].split("/")[1]
        space_users = enrolment.list_users(space_id)
        return self.responses.create_user_list_dialog(space_users)

    def _validate_url(self, url: str, context_sources: List[str]) -> bool:
        """
        Validate URL exists and is accessible
        """
        if url in context_sources:
            return True

        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            return response.status_code in [200, 302, 403] or (
                "advisernet" in url and response.status_code == 302
            )
        except requests.RequestException as e:
            logger.error(f"Error checking URL {url}: {str(e)}")
            return False

    def _get_domain(self, url: str) -> str:
        """
        Extract and format domain from URL
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        if domain.startswith("www."):
            domain = domain[4:]

        if "advisernet" in url:
            domain = "advisernet"

        return domain

    def _build_follow_up_context(
        self,
        original_query: str,
        original_message: str,
        follow_up_questions: List[str],
        event: Dict[str, Any],
    ) -> str:
        """
        Build context string from follow up answers
        """
        context = f"Original Query: {original_query}\n\n"
        context += f"Original response: {original_message}\n\n"
        context += "Follow-up Questions and Answers:\n"

        for i, question in enumerate(follow_up_questions, start=1):
            answer_key = f"follow_up_answer_{i}"
            if answer_key in event["common"]["formInputs"]:
                answer = event["common"]["formInputs"][answer_key]["stringInputs"][
                    "value"
                ][0]
                context += f"Q: {question}\nA: {answer}\n\n"

        return context

    def _create_survey_card(self, user: str, thread_id: str) -> Dict[str, Any]:
        """
        Create survey card
        """
        post_call_survey_questions = get_survey(user)
        return self.get_post_call_survey_card(post_call_survey_questions, thread_id)

    async def continue_existing_interaction(
        self, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Continue existing interaction
        """
        await self.update_survey_card_in_adviser_space(
            space_id=event["space"]["name"].split("/")[1],
            message_id=event["message"]["name"].split("/")[3],
            card=self.messages.CONTINUE_EXISTING_INTERACTION,
        )
        return await self.handle_proceed_query(event)

    async def end_existing_interaction(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        End an existing interaction
        """
        user = event["user"]["email"]
        user_space = event["space"]["name"].split("/")[1]
        message_id = event["message"]["name"].split("/")[3]
        survey_thread_id = event["common"]["parameters"]["thread_id"]
        message_event = json.loads(event["common"]["parameters"]["message_event"])
        message_event = message_event["message"]["text"]
        card = self.messages.END_EXISTING_INTERACTION
        card = self.append_survey_questions(card, survey_thread_id, user, message_event)
        await self.update_survey_card_in_adviser_space(
            space_id=user_space,
            message_id=message_id,
            card=card,
        )
        return self.responses.NO_CONTENT

    async def finalise_caddy_call(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalise Caddy call
        """
        survey_card = json.loads(event["common"]["parameters"]["survey"])
        thread_id = event["message"]["thread"]["name"].split("/")[3]
        user_space = event["space"]["name"].split("/")[1]
        user = event["user"]["email"]

        self.caddy_instance.mark_call_complete(user=user, thread_id=thread_id)
        survey_required = check_if_survey_required(user)

        if survey_required:
            await self.update_survey_card_in_adviser_space(
                space_id=user_space,
                message_id=event["message"]["name"].split("/")[3],
                card=self.messages.CALL_COMPLETE,
            )
            await self.run_survey(survey_card, user_space, thread_id)

        return self.responses.NO_CONTENT

    def append_survey_questions(
        self,
        card: Dict[str, Any],
        thread_id: str,
        user: str,
        event: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Append survey questions to card
        """
        survey_card = self.get_survey_card(thread_id, user, event)
        card["cardsV2"][0]["card"]["sections"].append(
            survey_card["cardsV2"][0]["card"]["sections"][0]
        )
        return card

    def get_post_call_survey_card(
        self,
        post_call_survey_questions: List[Dict[str, Any]],
        thread_id: str,
        event: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create post-call survey card
        """
        card = {
            "cardsV2": [
                {
                    "cardId": "postCallSurvey",
                    "card": {"sections": []},
                },
            ],
        }

        section = {"widgets": []}
        button_section = {"buttonList": {"buttons": []}}

        copy_button = {
            "text": "Copy caddy message",
            "onClick": {
                "action": {
                    "function": "copy_caddy_response",
                    "parameters": [
                        {"key": "threadId", "value": thread_id},
                        {"key": "event", "value": event},
                    ],
                }
            },
        }
        button_section["buttonList"]["buttons"].append(copy_button)

        for question_dict in post_call_survey_questions:
            question = question_dict["question"]
            values = question_dict["values"]

            question_dropdown = {
                "selectionInput": {
                    "name": question,
                    "label": question,
                    "type": "DROPDOWN",
                    "items": [],
                }
            }

            for value in values:
                question_dropdown["selectionInput"]["items"].append(
                    {"text": value, "value": value, "selected": False}
                )

            section["widgets"].append(question_dropdown)

        submit_button = {
            "text": "Submit",
            "onClick": {
                "action": {
                    "function": "survey_response",
                    "parameters": [
                        {"key": "threadId", "value": thread_id},
                        {"key": "event", "value": event},
                    ],
                }
            },
        }
        button_section["buttonList"]["buttons"].append(submit_button)

        section["widgets"].append(button_section)
        card["cardsV2"][0]["card"]["sections"].append(section)

        return card

    def get_survey_card(
        self, thread_id: str, user: str, event: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get survey card
        """
        post_call_survey_questions = get_survey(user)
        return self.get_post_call_survey_card(
            post_call_survey_questions, thread_id, event
        )

    def _create_approval_event(
        self, event: Dict[str, Any]
    ) -> Tuple[ApprovalEvent, Dict[str, Any]]:
        """
        Create approval event and response card from event data
        """
        try:
            card_content = json.loads(event["common"]["parameters"]["aiResponse"])

            supervisor_notes = (
                event.get("common", {})
                .get("formInputs", {})
                .get("supervisor_notes", {})
                .get("stringInputs", {})
                .get("value", [""])[0]
            )
            approver_name = event.get("user", {}).get("email", "")

            approval_event = ApprovalEvent(
                response_id=event["common"]["parameters"]["responseId"],
                thread_id=event["common"]["parameters"]["threadId"],
                approver_email=approver_name,
                approved=True,
                approval_timestamp=datetime.now(),
                user_response_timestamp=datetime.now(),
                supervisor_message=supervisor_notes,
            )

            return approval_event, card_content

        except KeyError as e:
            logger.error(f"Missing required field in approval event data: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse card content: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating approval event: {e}")
            raise

    def _create_rejection_event(self, event: Dict[str, Any]) -> ApprovalEvent:
        """
        Create rejection event from event data
        """
        try:
            supervisor_notes = (
                event.get("common", {})
                .get("formInputs", {})
                .get("supervisor_notes", {})
                .get("stringInputs", {})
                .get("value", [""])[0]
            )
            approver_name = event.get("user", {}).get("email", "")

            rejection_event = ApprovalEvent(
                response_id=event["common"]["parameters"]["responseId"],
                thread_id=event["common"]["parameters"]["threadId"],
                approver_email=approver_name,
                approved=False,
                approval_timestamp=datetime.now(),
                user_response_timestamp=datetime.now(),
                supervisor_message=supervisor_notes,
            )

            return rejection_event

        except KeyError as e:
            logger.error(f"Missing required field in rejection event data: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating rejection event: {e}")
            raise

    async def handle_supervisor_dialog(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle supervisor dialog actions
        """
        match event["message"]["annotations"][0]["slashCommand"]["commandName"]:
            case "/addUser":
                await self.add_user(event)
            case "/removeUser":
                await self.remove_user(event)
        return self.responses.SUCCESS_DIALOG
