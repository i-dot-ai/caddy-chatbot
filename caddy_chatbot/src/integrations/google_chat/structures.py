import os
import json
import re
import requests
from typing import Dict, Any, List, Tuple, Optional, Union
from datetime import datetime
from caddy_core.models import (
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
from langchain_aws import ChatBedrock

from urllib.parse import urlparse, urlunparse

from thefuzz import fuzz


class GoogleChat:
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

        caddy_message = self.format_message(event)
        if caddy_message == "PII Detected":
            return self.responses.NO_CONTENT

        await self.caddy_instance.handle_message(caddy_message)
        return self.responses.ACCEPTED

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
        action_name = event["action"]["actionMethodName"]
        match action_name:
            case "Approved":
                return await self.handle_supervisor_approval(event)
            case "Rejected":
                return await self.handle_supervisor_rejection(event)
            case "receiveDialog":
                return await self.handle_supervisor_dialog(event)
            case _:
                logger.warning(f"Unhandled supervisor card action: {action_name}")
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
                    return await self.list_space_users(event)
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
            self.send_existing_call_reminder(
                space_id=space_id,
                thread_id=thread_id,
                call_start_time=user_record["callStart"],
                survey_thread_id=user_record["activeThreadId"],
                event=event,
            )
            return True
        return False

    def format_message(self, event: Dict[str, Any]) -> CaddyMessageEvent:
        """
        Format the incoming message into a CaddyMessageEvent
        """
        space_id = event["space"]["name"].split("/")[1]
        thread_id = (
            event["message"]["thread"]["name"].split("/")[3]
            if "thread" in event["message"]
            else None
        )
        message_string = event["message"]["text"].replace("@Caddy", "").strip()

        if "proceed" not in event:
            pii_identified = analyse(message_string)
            if pii_identified:
                # Optionally redact PII from the message by importing redact from services.anonymise
                # message_string = redact(message_string, pii_identified)

                self.send_pii_warning_to_adviser_space(
                    space_id=space_id,
                    thread_id=thread_id,
                    message=self.messages.PII_DETECTED,
                    message_event=event,
                )
                return "PII Detected"

        thread_id, message_id = self.send_dynamic_to_adviser_space(
            response_type="cardsV2",
            space_id=space_id,
            thread_id=thread_id,
            message=self.messages.PROCESSING_MESSAGE,
        )

        return CaddyMessageEvent(
            type="PROCESS_CHAT_MESSAGE",
            user=event["user"]["email"],
            name=event["user"]["name"],
            space_id=space_id,
            thread_id=thread_id,
            message_id=message_id,
            message_string=message_string,
            source_client=self.client,
            timestamp=event["eventTime"],
        )

    def send_existing_call_reminder(
        self,
        space_id: str,
        thread_id: str,
        call_start_time: str,
        survey_thread_id: str,
        event: Dict[str, Any],
    ):
        """
        Send a reminder for an existing call
        """
        self.caddy.spaces().messages().create(
            parent=f"spaces/{space_id}",
            body=self.responses.existing_call_reminder(
                event, space_id, thread_id, call_start_time, survey_thread_id
            ),
            messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
        ).execute()

    def send_pii_warning_to_adviser_space(
        self, space_id: str, thread_id: str, message: str, message_event: Dict[str, Any]
    ):
        """
        Send a PII warning to the adviser space
        """
        self.caddy.spaces().messages().create(
            parent=f"spaces/{space_id}",
            body={
                "cardsV2": [
                    {
                        "cardId": "PIIDetected",
                        "card": {
                            "sections": [
                                {
                                    "widgets": [
                                        {"textParagraph": {"text": message}},
                                    ],
                                },
                                {
                                    "widgets": [
                                        {
                                            "buttonList": {
                                                "buttons": [
                                                    {
                                                        "text": "Proceed without redaction",
                                                        "onClick": {
                                                            "action": {
                                                                "function": "Proceed",
                                                                "parameters": [
                                                                    {
                                                                        "key": "message_event",
                                                                        "value": json.dumps(
                                                                            message_event
                                                                        ),
                                                                    },
                                                                ],
                                                            }
                                                        },
                                                    },
                                                    {
                                                        "text": "Edit original query",
                                                        "onClick": {
                                                            "action": {
                                                                "function": "edit_query_dialog",
                                                                "interaction": "OPEN_DIALOG",
                                                                "parameters": [
                                                                    {
                                                                        "key": "message_event",
                                                                        "value": json.dumps(
                                                                            message_event
                                                                        ),
                                                                    },
                                                                ],
                                                            }
                                                        },
                                                    },
                                                ]
                                            }
                                        }
                                    ],
                                },
                            ],
                        },
                    },
                ],
                "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
            },
            messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
        ).execute()

    def send_dynamic_to_adviser_space(
        self, response_type: str, space_id: str, message: Dict[str, Any], thread_id: str
    ) -> Tuple[str, str]:
        """
        Send a dynamic message to the adviser space
        """
        match response_type:
            case "text":
                response = (
                    self.caddy.spaces()
                    .messages()
                    .create(
                        parent=f"spaces/{space_id}",
                        body={
                            "text": message,
                            "thread": {
                                "name": f"spaces/{space_id}/threads/{thread_id}"
                            },
                        },
                        messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
                    )
                    .execute()
                )
            case "cardsV2":
                response = (
                    self.caddy.spaces()
                    .messages()
                    .create(
                        parent=f"spaces/{space_id}",
                        body={
                            "cardsV2": message["cardsV2"],
                            "thread": {
                                "name": f"spaces/{space_id}/threads/{thread_id}"
                            },
                        },
                        messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
                    )
                    .execute()
                )

        thread_id = response["thread"]["name"].split("/")[3]
        message_id = response["name"].split("/")[3]

        return thread_id, message_id

    async def handle_proceed_query(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a proceed query event
        """
        event = json.loads(event["common"]["parameters"]["message_event"])
        event["proceed"] = True
        caddy_message = self.format_message(event)
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
        self.send_message_to_supervisor_space(
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
        self.update_message_in_adviser_space(
            message_type="cardsV2",
            space_id=caddy_message.space_id,
            message_id=caddy_message.message_id,
            message={"cardsV2": control_group_card},
        )
        return self.responses.NO_CONTENT

    async def get_edit_query_dialog(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the edit query dialog
        """
        event = json.loads(event["common"]["parameters"]["message_event"])
        message_string = event["message"]["text"].replace("@Caddy", "").strip()
        edit_query_dialog = self.edit_query_dialog(event, message_string)
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
        caddy_message = self.format_message(event)
        await self.caddy_instance.handle_message(caddy_message)
        return self.responses.ACCEPTED

    async def continue_existing_interaction(
        self, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Continue an existing interaction
        """
        self.update_survey_card_in_adviser_space(
            space_id=event["space"]["name"].split("/")[1],
            message_id=event["message"]["name"].split("/")[3],
            card=self.messages.CONTINUE_EXISTING_INTERACTION,
        )
        return self.handle_proceed_query(event)

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
        self.update_survey_card_in_adviser_space(
            space_id=user_space,
            message_id=message_id,
            card=card,
        )
        return self.responses.NO_CONTENT

    async def handle_survey_response(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a survey response
        """
        user = event["user"]["email"]
        survey_responses = event["common"]["formInputs"]
        thread_id = event["common"]["parameters"]["threadId"]
        card = event["message"]["cardsV2"]
        space_id = event["space"]["name"].split("/")[1]
        message_id = event["message"]["name"].split("/")[3]
        message_event = event["common"]["parameters"]["event"]

        questions_and_values = []
        for question, response in survey_responses.items():
            value = response["stringInputs"]["value"][0]
            questions_and_values.append({question: value})

        self.caddy_instance.store_survey_response(thread_id, questions_and_values)

        card[0]["card"]["sections"].pop()
        if message_event:
            card[0]["card"]["sections"].pop()
        card[0]["card"]["sections"].append(self.messages.SURVEY_COMPLETE_WIDGET)

        self.caddy_instance.mark_call_complete(user=user, thread_id=thread_id)

        self.update_survey_card_in_adviser_space(
            space_id=space_id, message_id=message_id, card={"cardsV2": card}
        )
        return message_event if message_event else self.responses.NO_CONTENT

    async def finalise_caddy_call(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalise a Caddy call
        """
        survey_card = json.loads(event["common"]["parameters"]["survey"])
        thread_id = event["message"]["thread"]["name"].split("/")[3]
        user_space = event["space"]["name"].split("/")[1]
        user = event["user"]["email"]
        self.caddy_instance.mark_call_complete(user=user, thread_id=thread_id)
        survey_required = check_if_survey_required(user)
        if survey_required:
            self.update_survey_card_in_adviser_space(
                space_id=user_space,
                message_id=event["message"]["name"].split("/")[3],
                card=self.messages.CALL_COMPLETE,
            )
            self.run_survey(survey_card, user_space, thread_id)
        return self.responses.NO_CONTENT

    async def handle_supervisor_approval(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle supervisor approval
        """
        user, user_space, thread_id, approval_event = self.received_approval(event)
        self.caddy_instance.store_approver_event(thread_id, approval_event)
        return self.responses.NO_CONTENT

    async def handle_supervisor_rejection(
        self, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle supervisor rejection
        """
        self.handle_supervisor_rejection_internal(event)
        return self.responses.NO_CONTENT

    async def handle_supervisor_dialog(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle supervisor dialog actions
        """
        match event["message"]["annotations"][0]["slashCommand"]["commandName"]:
            case "/addUser":
                self.add_user(event)
            case "/removeUser":
                self.remove_user(event)
        return self.responses.SUCCESS_DIALOG

    async def list_space_users(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        List users in the supervision space
        """
        supervision_space_id = event["space"]["name"].split("/")[1]
        space_name = event["space"]["displayName"]
        space_users = enrolment.list_users(supervision_space_id)
        return self.user_list_dialog(
            supervision_users=space_users, space_display_name=space_name
        )

    def update_message_in_adviser_space(
        self, message_type: str, space_id: str, message_id: str, message: Dict[str, Any]
    ):
        """
        Update a message in the adviser space
        """
        match message_type:
            case "text":
                self.caddy.spaces().messages().patch(
                    name=f"spaces/{space_id}/messages/{message_id}",
                    body={"text": message},
                    updateMask="text",
                ).execute()
            case "cardsV2":
                self.caddy.spaces().messages().patch(
                    name=f"spaces/{space_id}/messages/{message_id}",
                    body=message,
                    updateMask="cardsV2",
                ).execute()

    async def send_status_update(
        self, event: CaddyMessageEvent, status: str, activity_id: str = None
    ):
        """
        Send a status update for Google Chat
        """
        status_cards = {
            "processing": self.messages.PROCESSING_MESSAGE,
            "composing": self.messages.COMPOSING_MESSAGE,
            "composing_retry": self.messages.COMPOSING_MESSAGE_RETRY,
            "request_failure": self.messages.REQUEST_FAILURE,
            "supervisor_reviewing": self.messages.SUPERVISOR_REVIEWING_RESPONSE,
            "awaiting_approval": self.messages.AWAITING_SUPERVISOR_APPROVAL,
        }

        if status in status_cards:
            card_content = status_cards[status]

            if activity_id:
                self.update_message_in_adviser_space(
                    message_type="cardsV2",
                    space_id=event.space_id,
                    message_id=activity_id,
                    message=card_content,
                )
                return activity_id
            else:
                thread_id, message_id = self.send_dynamic_to_adviser_space(
                    response_type="cardsV2",
                    space_id=event.space_id,
                    message=card_content,
                    thread_id=event.thread_id,
                )
                return message_id
        else:
            logger.error(f"Unknown status: {status}")
            return None

    async def send_supervision_request(
        self,
        event: Union[CaddyMessageEvent, SupervisionEvent],
        status: str,
        supervisor_space: str,
        activity_id: str = None,
    ):
        """
        Send a supervision request update
        """
        supervision_cards = {
            "failed": self.responses.supervisor_request_failed,
            "processing": self.responses.supervisor_request_processing,
            "awaiting": self.responses.supervisor_request_pending,
            "approved": self.responses.supervisor_request_approved,
            "rejected": self.responses.supervisor_request_rejected,
            "follow_up": self.responses.supervisor_request_follow_up_details,
        }

        if status in supervision_cards:
            user = event.user if isinstance(event, CaddyMessageEvent) else event.user
            message = (
                event.message_string
                if isinstance(event, CaddyMessageEvent)
                else event.llmPrompt
            )
            card_content = supervision_cards[status](user, message)

            if activity_id:
                self.update_message_in_supervisor_space(
                    space_id=supervisor_space,
                    message_id=activity_id,
                    new_message=card_content,
                )
                return activity_id
            else:
                thread_id, message_id = self.send_message_to_supervisor_space(
                    space_id=supervisor_space,
                    message=card_content,
                )
                return message_id
        else:
            logger.error(f"Unknown supervision status: {status}")
            return None

    def update_survey_card_in_adviser_space(
        self, space_id: str, message_id: str, card: Dict[str, Any]
    ):
        """
        Update a survey card in the adviser space
        """
        self.caddy.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            body=card,
            updateMask="cardsV2",
        ).execute()

    def edit_query_dialog(
        self, message_event: Dict[str, Any], message_string: str
    ) -> Dict[str, Any]:
        """
        Create an edit query dialog
        """
        return {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {
                    "dialog": {
                        "body": {
                            "sections": [
                                {
                                    "header": "PII Detected: Edit query",
                                    "widgets": [
                                        {
                                            "textInput": {
                                                "label": "Please edit your original query to remove PII",
                                                "type": "MULTIPLE_LINE",
                                                "name": "editedQuery",
                                                "value": message_string,
                                            }
                                        },
                                        {
                                            "buttonList": {
                                                "buttons": [
                                                    {
                                                        "text": "Submit edited query",
                                                        "onClick": {
                                                            "action": {
                                                                "function": "receiveEditedQuery",
                                                                "parameters": [
                                                                    {
                                                                        "key": "message_event",
                                                                        "value": json.dumps(
                                                                            message_event
                                                                        ),
                                                                    },
                                                                ],
                                                            }
                                                        },
                                                    }
                                                ]
                                            },
                                            "horizontalAlignment": "END",
                                        },
                                    ],
                                }
                            ]
                        }
                    }
                },
            }
        }

    async def send_survey_complete_message(self, caddy_message: CaddyMessageEvent):
        """
        Send a survey complete message
        """
        self.update_message_in_adviser_space(
            message_type="text",
            space_id=caddy_message.space_id,
            message_id=caddy_message.message_id,
            message=self.messages.SURVEY_ALREADY_COMPLETED,
        )

    def run_survey(self, survey_card: Dict[str, Any], user_space: str, thread_id: str):
        """
        Run a survey in the adviser space given a survey card input

        Args:
            survey_card (dict): The survey card to run
            user_space (str): The space ID of the user
            thread_id (str): The thread ID of the conversation

        Returns:
            None
        """
        self.send_dynamic_to_adviser_space(
            response_type="cardsV2",
            space_id=user_space,
            message=survey_card,
            thread_id=thread_id,
        )

    def append_survey_questions(
        self,
        card: Dict[str, Any],
        thread_id: str,
        user: str,
        event: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Append survey questions to a card
        """
        survey_card = self.get_survey_card(thread_id, user, event)
        card["cardsV2"][0]["card"]["sections"].append(
            survey_card["cardsV2"][0]["card"]["sections"][0]
        )
        return card

    def get_survey_card(
        self, thread_id: str, user: str, event: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get a survey card
        """
        post_call_survey_questions = get_survey(user)
        return self.get_post_call_survey_card(
            post_call_survey_questions, thread_id, event
        )

    def get_post_call_survey_card(
        self,
        post_call_survey_questions: List[Dict[str, Any]],
        thread_id: str,
        event: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a post-call survey card
        """
        card = {
            "cardsV2": [
                {
                    "cardId": "postCallSurvey",
                    "card": {
                        "sections": [],
                    },
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

    def received_approval(
        self, event: Dict[str, Any]
    ) -> Tuple[str, str, str, ApprovalEvent]:
        """
        Process a received approval
        """
        card = json.loads(event["common"]["parameters"]["aiResponse"])
        user_space = event["common"]["parameters"]["conversationId"]
        approver = event["user"]["email"]
        response_id = event["common"]["parameters"]["responseId"]
        thread_id = event["common"]["parameters"]["threadId"]
        supervisor_space = event["space"]["name"].split("/")[1]
        message_id = event["message"]["name"].split("/")[3]
        supervisor_card = {"cardsV2": event["message"]["cardsV2"]}
        user_message_id = event["common"]["parameters"]["messageId"]
        request_message_id = event["common"]["parameters"]["newRequestId"]
        request_card = json.loads(event["common"]["parameters"]["requestApproved"])
        user_email = event["common"]["parameters"]["userEmail"]
        supervisor_notes = event["common"]["formInputs"]["supervisor_notes"][
            "stringInputs"
        ]["value"][0]

        approved_card = self.create_approved_card(card, approver, supervisor_notes)

        client_friendly_button = {
            "buttonList": {
                "buttons": [
                    {
                        "text": "Convert to Client Friendly",
                        "onClick": {
                            "action": {
                                "function": "convert_to_client_friendly",
                                "interaction": "OPEN_DIALOG",
                                "parameters": [
                                    {
                                        "key": "card_content",
                                        "value": json.dumps(approved_card),
                                    },
                                ],
                            }
                        },
                    }
                ]
            }
        }

        approved_card["cardsV2"][0]["card"]["sections"].append(
            {"widgets": [client_friendly_button]}
        )

        domain = user_email.split("@")[1]
        _, office = enrolment.check_domain_status(domain)
        included_in_rct = enrolment.check_rct_status(office)
        if included_in_rct:
            approved_card = self.append_survey_questions(
                approved_card, thread_id, user_email
            )

        self.update_dynamic_message_in_adviser_space(
            space_id=user_space,
            message_id=user_message_id,
            response_type="cardsV2",
            message=approved_card,
        )

        updated_supervision_card = self.create_updated_supervision_card(
            supervision_card=supervisor_card,
            approver=approver,
            approved=True,
            supervisor_message=supervisor_notes,
        )
        self.update_message_in_supervisor_space(
            space_id=supervisor_space,
            message_id=message_id,
            new_message=updated_supervision_card,
        )

        self.update_message_in_supervisor_space(
            space_id=supervisor_space,
            message_id=request_message_id,
            new_message=request_card,
        )

        approval_event = ApprovalEvent(
            response_id=response_id,
            thread_id=thread_id,
            approver_email=approver,
            approved=True,
            approval_timestamp=event["eventTime"],
            user_response_timestamp=datetime.now(),
            supervisor_message=supervisor_notes,
        )

        return user_email, user_space, thread_id, approval_event

    def handle_supervisor_rejection_internal(self, event: Dict[str, Any]):
        """
        Handle supervisor rejection internally
        """
        supervisor_card = {"cardsV2": event["message"]["cardsV2"]}
        user_space = event["common"]["parameters"]["conversationId"]
        approver = event["user"]["email"]
        response_id = event["common"]["parameters"]["responseId"]
        supervisor_space = event["space"]["name"].split("/")[1]
        message_id = event["message"]["name"].split("/")[3]
        user_message_id = event["common"]["parameters"]["messageId"]
        supervisor_message = event["common"]["formInputs"]["supervisor_notes"][
            "stringInputs"
        ]["value"][0]
        thread_id = event["common"]["parameters"]["threadId"]
        request_message_id = event["common"]["parameters"]["newRequestId"]
        request_card = json.loads(event["common"]["parameters"]["requestRejected"])
        user_email = event["common"]["parameters"]["userEmail"]

        rejection_card = self.responses.supervisor_rejection(
            approver=approver, supervisor_message=supervisor_message
        )

        domain = user_email.split("@")[1]
        _, office = enrolment.check_domain_status(domain)
        included_in_rct = enrolment.check_rct_status(office)
        if included_in_rct:
            rejection_card = self.append_survey_questions(
                rejection_card, thread_id, user_email
            )

        self.update_message_in_supervisor_space(
            space_id=supervisor_space,
            message_id=request_message_id,
            new_message=request_card,
        )

        self.update_dynamic_message_in_adviser_space(
            space_id=user_space,
            message_id=user_message_id,
            response_type="cardsV2",
            message=rejection_card,
        )

        updated_supervision_card = self.create_updated_supervision_card(
            supervision_card=supervisor_card,
            approver=approver,
            approved=False,
            supervisor_message=supervisor_message,
        )
        self.update_message_in_supervisor_space(
            space_id=supervisor_space,
            message_id=message_id,
            new_message=updated_supervision_card,
        )

        rejection_event = ApprovalEvent(
            response_id=response_id,
            thread_id=thread_id,
            approver_email=approver,
            approved=False,
            approval_timestamp=event["eventTime"],
            user_response_timestamp=datetime.now(),
            supervisor_message=supervisor_message,
        )

        self.caddy_instance.store_approver_event(thread_id, rejection_event)

    def create_approved_card(
        self, card: Dict[str, Any], approver: str, supervisor_notes: str
    ) -> Dict[str, Any]:
        """
        Create an approved card
        """
        card["cardsV2"][0]["card"]["sections"].insert(
            0, self.responses.approval_json_widget(approver, supervisor_notes)
        )
        return card

    def create_updated_supervision_card(
        self,
        supervision_card: Dict[str, Any],
        approver: str,
        approved: bool,
        supervisor_message: str,
    ) -> Dict[str, Any]:
        """
        Create an updated supervision card
        """
        if approved:
            approval_section = self.responses.approval_json_widget(
                approver, supervisor_notes=supervisor_message
            )
        else:
            approval_section = self.responses.rejection_json_widget(
                approver, supervisor_message
            )

        card_for_approval_sections = list(
            supervision_card["cardsV2"][0]["card"]["sections"]
        )
        card_for_approval_sections.pop()  # remove thumbs up/ thumbs down section
        card_for_approval_sections.append(approval_section)

        supervision_card["cardsV2"][0]["card"]["sections"] = card_for_approval_sections

        return supervision_card

    def update_message_in_supervisor_space(
        self, space_id: str, message_id: str, new_message: Dict[str, Any]
    ):
        """
        Update a message in the supervisor space
        """
        self.supervisor.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            updateMask="cardsV2",
            body=new_message,
        ).execute()

    def update_dynamic_message_in_adviser_space(
        self,
        space_id: str,
        message_id: str,
        response_type: str,
        message: Dict[str, Any],
    ):
        """
        Update a dynamic message in the adviser space
        """
        self.caddy.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            updateMask=response_type,
            body=message,
        ).execute()

    def add_user(self, event: Dict[str, Any]):
        """
        Add a user to Caddy
        """
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]
        role = event["common"]["formInputs"]["role"]["stringInputs"]["value"][0]
        supervisor_space_id = event["space"]["name"].split("/")[1]

        try:
            enrolment.register_user(user, role, supervisor_space_id)
        except Exception as error:
            logger.error(f"Adding user failed: {error}")

    def remove_user(self, event: Dict[str, Any]):
        """
        Remove a user from Caddy
        """
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]

        try:
            enrolment.remove_user(user)
        except Exception as error:
            logger.error(f"Removing user failed: {error}")

    def user_list_dialog(
        self, supervision_users: str, space_display_name: str
    ) -> Dict[str, Any]:
        """
        Create a user list dialog
        """
        return {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {
                    "dialog": {
                        "body": {
                            "sections": [
                                {
                                    "header": f"Supervision users for {space_display_name}",
                                    "widgets": [
                                        {"textParagraph": {"text": supervision_users}}
                                    ],
                                }
                            ]
                        }
                    }
                },
            }
        }

    def create_card(
        self, llm_response: str, context_sources: List[str]
    ) -> Dict[str, Any]:
        """
        Takes in the LLM response and context sources, extracts citations, fuzzy matches them
        with actual context sources, and adds them as reference links in the Google Chat card

        Args:
            llm_response: Response from LLM
            context_sources: List of actual source URLs from the context

        Returns:
            Google Chat Card
        """
        card = {
            "cardsV2": [
                {
                    "cardId": "aiResponseCard",
                    "card": {
                        "sections": [],
                    },
                },
            ],
        }

        reference_links_section = {"header": "Reference links", "widgets": []}

        urls = re.findall(
            r"<ref>((?:SOURCE_URL:)?(http[s]?://[^\s>]+))</ref>", llm_response
        )

        processed_urls = []
        ref = 0

        for i, (full_url, base_url) in enumerate(urls):
            if full_url in processed_urls:
                continue

            url_to_check = full_url.replace("SOURCE_URL:", "")

            url_parts = urlparse(url_to_check)
            base_url = urlunparse(url_parts._replace(fragment=""))
            fragment = url_parts.fragment

            best_match = max(context_sources, key=lambda x: fuzz.ratio(base_url, x))
            match_score = fuzz.ratio(base_url, best_match)

            logger.debug(f"Cited: {url_to_check}")
            logger.debug(f"Best match: {best_match}")
            logger.debug(f"Match score: {match_score}")

            use_url = best_match if match_score > 95 else base_url

            url_valid = False
            if use_url in context_sources:
                url_valid = True
            else:
                try:
                    response = requests.head(use_url, timeout=5, allow_redirects=True)
                    if response.status_code in [200, 302, 403] or (
                        "advisernet" in use_url and response.status_code == 302
                    ):
                        url_valid = True
                    else:
                        logger.warning(
                            f"URL {use_url} returned status code {response.status_code}"
                        )
                except requests.RequestException as e:
                    logger.error(f"Error checking URL {use_url}: {str(e)}")

            if url_valid:
                ref += 1
                parsed_url = urlparse(use_url)
                domain = parsed_url.netloc

                if domain.startswith("www."):
                    domain = domain[4:]

                if "advisernet" in use_url:
                    domain = "advisernet"

                resource = domain

                full_use_url = f"{use_url}#{fragment}" if fragment else use_url

                llm_response = llm_response.replace(
                    f"<ref>{full_url}</ref>",
                    f'<a href="{full_use_url}">[{ref} - {resource}]</a>',
                )

                reference_link = {
                    "textParagraph": {
                        "text": f'<a href="{full_use_url}">[{ref}- {resource}] {full_use_url}</a>'
                    }
                }
                reference_links_section["widgets"].append(reference_link)

                processed_urls.append(full_url)
            else:
                llm_response = llm_response.replace(f"<ref>{full_url}</ref>", "")

        llm_response_section = {
            "widgets": [
                {"textParagraph": {"text": llm_response}},
            ],
        }

        card["cardsV2"][0]["card"]["sections"].append(llm_response_section)

        if reference_links_section["widgets"]:
            card["cardsV2"][0]["card"]["sections"].append(reference_links_section)

        return card

    def send_message_to_supervisor_space(
        self, space_id: str, message: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Send a message to the supervisor space
        """
        response = (
            self.supervisor.spaces()
            .messages()
            .create(parent=f"spaces/{space_id}", body=message)
            .execute()
        )

        thread_id = response["thread"]["name"].split("/")[3]
        message_id = response["name"].split("/")[3]

        return thread_id, message_id

    def respond_to_supervisor_thread(
        self, space_id: str, message: Dict[str, Any], thread_id: str
    ) -> str:
        """
        Creates a message within a supervisor thread

        Args:
            space_id (str): id of the supervisor space
            message (dict): card to be sent
            thread_id (str): id of the supervisor space thread to create message in

        Returns:
            message_id: Id of the new message
        """
        response = (
            self.supervisor.spaces()
            .messages()
            .create(
                parent=f"spaces/{space_id}",
                body={
                    "cardsV2": message["cardsV2"],
                    "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
                },
                messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
            )
            .execute()
        )

        message_id = response["name"].split("/")[3]
        return message_id

    def delete_message_in_adviser_space(self, space_id: str, message_id: str):
        """
        Delete a message in the adviser space
        """
        self.caddy.spaces().messages().delete(
            name=f"spaces/{space_id}/messages/{message_id}"
        ).execute()

    def similar_question_dialog(
        self, similar_question: str, question_answer: str, similarity: float
    ) -> Dict[str, Any]:
        """
        Create a similar question dialog
        """
        return {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {
                    "dialog": {
                        "body": {
                            "sections": [
                                {
                                    "header": f'<font color="#004f88"><b>{similar_question}</b></font>',
                                    "widgets": [
                                        {"textParagraph": {"text": question_answer}},
                                        {
                                            "textParagraph": {
                                                "text": f'<font color="#004f88"><b>{similarity}% Match</b></font>'
                                            }
                                        },
                                    ],
                                }
                            ]
                        }
                    }
                },
            }
        }

    def call_complete_confirmation(self, user: str, user_space: str, thread_id: str):
        """
        Send a call complete confirmation
        """
        survey_card = self.get_survey_card(thread_id, user)
        call_complete_card = self.responses.call_complete_card(survey_card)

        self.send_dynamic_to_adviser_space(
            response_type="cardsV2",
            space_id=user_space,
            message=call_complete_card,
            thread_id=thread_id,
        )

    def run_new_survey(
        self,
        user: str,
        thread_id: str,
        user_space: str,
        reminder_thread_id: Optional[str] = None,
    ):
        """
        Run a new survey
        """
        post_call_survey_questions = get_survey(thread_id, user)
        survey_card = self.get_post_call_survey_card(
            post_call_survey_questions, thread_id
        )

        thread_for_survey = reminder_thread_id if reminder_thread_id else thread_id

        self.send_dynamic_to_adviser_space(
            response_type="cardsV2",
            space_id=user_space,
            message=survey_card,
            thread_id=thread_for_survey,
        )

    async def convert_to_client_friendly(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts the card content to a client-friendly version and returns it in a dialog.

        Args:
            event (Dict[str, Any]): The event containing the card content.

        Returns:
            Dict[str, Any]: The dialog response containing the client-friendly version.
        """
        card_content = json.loads(event["common"]["parameters"]["card_content"])

        llm = ChatBedrock(
            model_id=os.getenv("LLM"),
            region_name="eu-west-3",
            model_kwargs={"temperature": 0.3, "top_k": 5, "max_tokens": 2000},
        )

        prompt = f"""
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

        {card_content}

        Please provide the client-friendly version:
        """

        response = llm.invoke(prompt)
        client_friendly_content = response.content

        return self.client_friendly_dialog(client_friendly_content)

    def client_friendly_dialog(self, content: str) -> Dict[str, Any]:
        """
        Creates a dialog with the client-friendly content.

        Args:
            content (str): The client-friendly content.

        Returns:
            Dict[str, Any]: The dialog response.
        """
        return {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {
                    "dialog": {
                        "body": {
                            "sections": [
                                {
                                    "header": "Client Friendly Version",
                                    "widgets": [
                                        {"textParagraph": {"text": content}},
                                    ],
                                }
                            ]
                        }
                    }
                },
            }
        }

    async def process_follow_up_answers(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process follow-up answers and generate a new response
        """
        original_query = event["common"]["parameters"]["original_query"]
        original_message = event["common"]["parameters"]["original_message"]
        supervisor_message_id = event["common"]["parameters"]["supervisor_message_id"]
        supervisor_thread_id = event["common"]["parameters"]["supervisor_thread_id"]
        follow_up_questions = json.loads(
            event["common"]["parameters"]["follow_up_questions"]
        )

        follow_up_context = f"Original Query: {original_query}\n\n"
        follow_up_context += f"Original response: {original_message}\n\n"
        follow_up_context += "Follow-up Questions and Answers:\n"

        for i, question in enumerate(follow_up_questions, start=1):
            answer_key = f"follow_up_answer_{i}"
            if answer_key in event["common"]["formInputs"]:
                answer = event["common"]["formInputs"][answer_key]["stringInputs"][
                    "value"
                ][0]
                follow_up_context += f"Q: {question}\nA: {answer}\n\n"

        caddy_query = UserMessage(
            conversation_id=event["space"]["name"].split("/")[1],
            thread_id=event["message"]["thread"]["name"].split("/")[3],
            message_id=event["message"]["name"].split("/")[3],
            client=self.client,
            user_email=event["user"]["email"],
            message=original_query,
            message_sent_timestamp=str(datetime.now()),
            message_received_timestamp=datetime.now(),
        )

        status_message_id = await self.send_status_update(caddy_query, "processing")

        try:
            llm_output, context_sources = await self.caddy_instance.get_llm_response(
                caddy_query, is_follow_up=True, follow_up_context=follow_up_context
            )

            response_card = self.create_card(llm_output.message, context_sources)
            llm_response = self.caddy_instance.create_llm_response(
                caddy_query, llm_output, response_card, context_sources
            )
            self.caddy_instance.store_response(llm_response)

            supervision_event = self.caddy_instance.create_supervision_event(
                caddy_query, llm_response
            )
            await self.send_status_update(
                caddy_query, "supervisor_reviewing", status_message_id
            )
            await self.send_to_supervision(
                caddy_query,
                supervision_event,
                response_card,
                supervisor_message_id,
                supervisor_thread_id,
            )
        except Exception as error:
            await self.caddy_instance.handle_llm_error(
                caddy_query, error, status_message_id
            )

        return self.responses.ACCEPTED

    async def send_follow_up_questions(
        self,
        message_query: UserMessage,
        llm_output: LLMOutput,
        context_sources: List[str],
        status_message_id: Optional[str] = None,
        supervisor_message_id: Optional[str] = None,
        supervisor_thread_id: Optional[str] = None,
    ):
        follow_up_card = self.responses.create_follow_up_questions_card(
            llm_output, message_query, supervisor_message_id, supervisor_thread_id
        )
        if status_message_id:
            self.update_message_in_adviser_space(
                message_type="cardsV2",
                space_id=message_query.conversation_id,
                message_id=status_message_id,
                message=follow_up_card,
            )
        else:
            self.send_dynamic_to_adviser_space(
                response_type="cardsV2",
                space_id=message_query.conversation_id,
                message=follow_up_card,
                thread_id=message_query.thread_id,
            )

    async def send_to_supervision(
        self,
        message_query: UserMessage,
        supervision_event: SupervisionEvent,
        response_card: Dict,
        supervisor_message_id: Optional[str] = None,
        supervisor_thread_id: Optional[str] = None,
    ):
        supervisor_space = enrolment.get_designated_supervisor_space(
            message_query.user_email
        )

        if supervisor_message_id and supervisor_thread_id:
            supervision_card = self.responses.create_supervision_card(
                user_email=supervision_event.user,
                event=supervision_event,
                new_request_message_id=supervisor_message_id,
                request_approved=self.responses.supervisor_request_approved(
                    supervision_event.user, supervision_event.llmPrompt
                ),
                request_rejected=self.responses.supervisor_request_rejected(
                    supervision_event.user, supervision_event.llmPrompt
                ),
                card_for_approval=response_card,
            )
            self.update_message_in_supervisor_space(
                space_id=supervisor_space,
                message_id=supervisor_message_id,
                new_message=supervision_card,
            )
        else:
            supervision_message_id = await self.send_supervision_request(
                event=supervision_event,
                status="processing",
                supervisor_space=supervisor_space,
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

            self.update_message_in_supervisor_space(
                space_id=supervisor_space,
                message_id=supervision_message_id,
                new_message=supervision_card,
            )

        self.caddy_instance.store_approver_received_timestamp(supervision_event)
