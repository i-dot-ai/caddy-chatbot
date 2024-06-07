import os
import re
import json
from typing import Optional, Tuple, Dict


from pytz import timezone
from datetime import datetime

from caddy_core.models import CaddyMessageEvent, ApprovalEvent
from caddy_core.services.anonymise import analyse
from caddy_core.services.survey import get_survey, check_if_survey_required
from caddy_core.services import enrolment
from caddy_core.utils.tables import evaluation_table
from caddy_core import components as caddy
from integrations.google_chat import content, responses
from integrations.google_chat.auth import get_google_creds

from fastapi import status
from fastapi.responses import JSONResponse

from googleapiclient.discovery import build

from typing import List
from collections import deque


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

    def format_message(self, event):
        """
        Receives a message from Google Chat and formats it into a Caddy message event
        """
        space_id = event["space"]["name"].split("/")[1]
        thread_id = None
        if "thread" in event["message"]:
            thread_id = event["message"]["thread"]["name"].split("/")[3]

        message_string = event["message"]["text"].replace("@Caddy", "")

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

        caddy_message = CaddyMessageEvent(
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

        return caddy_message

    def send_message_to_adviser_space(self, space_id, thread_id, message) -> tuple:
        """
        Sends a message to the adviser space

        Args:
            space_id (str): The ID of the adviser space
            thread_id (str): The ID of the thread
            message (str): The message to be sent

        Returns:
            tuple: A tuple containing the thread_id and message_id of the sent message
        """
        response = (
            self.caddy.spaces()
            .messages()
            .create(
                parent=f"spaces/{space_id}",
                body={
                    "text": message,
                    "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
                },
                messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
            )
            .execute()
        )

        thread_id = response["thread"]["name"].split("/")[3]
        message_id = response["name"].split("/")[3]

        return thread_id, message_id

    def send_existing_call_reminder(
        self,
        space_id: str,
        thread_id: str,
        call_start_time: str,
        survey_thread_id: str,
        event,
    ):
        self.caddy.spaces().messages().create(
            parent=f"spaces/{space_id}",
            body=self.responses.existing_call_reminder(
                event, space_id, thread_id, call_start_time, survey_thread_id
            ),
            messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
        ).execute()

    def send_pii_warning_to_adviser_space(
        self, space_id: str, thread_id: str, message, message_event
    ):
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

    def update_message_in_adviser_space(
        self, message_type: str, space_id: str, message_id: str, message
    ) -> None:
        """
        Updates an existing text message in an adviser space

        Args:
            space_id (str): Space of the adviser
            message_id (str): Existing message that requires updating
            message: content to update message with

        Returns:
            None
        """
        match message_type:
            case "text":
                self.caddy.spaces().messages().patch(
                    name=f"spaces/{space_id}/messages/{message_id}",
                    body=message,
                    updateMask="text",
                ).execute()
            case "cardsV2":
                self.caddy.spaces().messages().patch(
                    name=f"spaces/{space_id}/messages/{message_id}",
                    body=message,
                    updateMask="cardsV2",
                ).execute()

    def update_survey_card_in_adviser_space(
        self, space_id: str, message_id: str, card: dict
    ) -> None:
        """
        Updates a survey card in the adviser space given a space ID, message ID, and card

        Args:
            space_id (str): The space ID of the user
            message_id (str): The message ID of the survey card
            card (dict): The card to update

        Returns:
            None
        """
        self.caddy.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            body=card,
            updateMask="cardsV2",
        ).execute()

    def get_edit_query_dialog(self, event):
        event = json.loads(event["common"]["parameters"]["message_event"])
        message_string = event["message"]["text"]
        message_string = message_string.replace("@Caddy", "")
        edit_query_dialog = self.edit_query_dialog(event, message_string)

        return JSONResponse(status_code=status.HTTP_200_OK, content=edit_query_dialog)

    def handle_survey_response(self, event):
        user = event["user"]["email"]
        survey_responses = event["common"]["formInputs"]
        threadId = event["common"]["parameters"]["threadId"]
        message_event = None
        card = event["message"]["cardsV2"]
        spaceId = event["space"]["name"].split("/")[1]
        messageId = event["message"]["name"].split("/")[3]
        message_event = event["common"]["parameters"]["event"]

        questions_and_values = []
        for question, response in survey_responses.items():
            value = response["stringInputs"]["value"][0]
            questions_and_values.append({question: value})

        evaluation_table.update_item(
            Key={"threadId": str(threadId)},
            UpdateExpression="set surveyResponse = list_append(if_not_exists(surveyResponse, :empty_list), :surveyResponse)",
            ExpressionAttributeValues={
                ":surveyResponse": questions_and_values,
                ":empty_list": [],
            },
            ReturnValues="UPDATED_NEW",
        )

        card[0]["card"]["sections"].pop()
        if message_event:
            card[0]["card"]["sections"].pop()
        card[0]["card"]["sections"].append(self.messages.SURVEY_COMPLETE_WIDGET)

        evaluation_table.update_item(
            Key={"threadId": str(threadId)},
            UpdateExpression="set surveyCompleteTimestamp = :timestamp",
            ExpressionAttributeValues={
                ":timestamp": datetime.now(timezone("Europe/London")).strftime(
                    "%d-%m-%Y %H:%M:%S"
                ),
            },
            ReturnValues="UPDATED_NEW",
        )
        caddy.mark_call_complete(user=user, thread_id=threadId)

        self.update_survey_card_in_adviser_space(
            space_id=spaceId, message_id=messageId, card={"cardsV2": card}
        )
        return message_event

    def similar_question_dialog(self, similar_question, question_answer, similarity):
        question_dialog = {
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
        return question_dialog

    def edit_query_dialog(self, message_event, message_string):
        edit_query_dialog = {
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
        return edit_query_dialog

    def run_survey(self, survey_card: dict, user_space: str, thread_id: str) -> None:
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

    def send_dynamic_to_adviser_space(
        self, response_type: str, space_id: str, message: dict, thread_id: str
    ) -> tuple:
        """
        Sends a dynamic message to the adviser space given a type of response

        Args:
            response_type (str): The type of response to send
            space_id (str): The space ID of the user
            message (dict): The message to send
            thread_id (str): The thread ID of the conversation

        Returns:
            thread_id, message_id
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

    def run_new_survey(
        self,
        user: str,
        thread_id: str,
        user_space: str,
        reminder_thread_id: Optional[str] = None,
    ) -> None:
        """
        Run a survey in the adviser space by getting the survey questions and values by providing a user to the get_survey function

        Args:
            survey_card (dict): The survey card to run
            user_space (str): The space ID of the user
            thread_id (str): The thread ID of the conversation

        Returns:
            None
        """
        post_call_survey_questions = get_survey(thread_id, user)

        survey_card = self.get_post_call_survey_card(
            post_call_survey_questions, thread_id
        )

        thread_for_survey = thread_id
        if reminder_thread_id:
            thread_for_survey = reminder_thread_id

        self.send_dynamic_to_adviser_space(
            response_type="cardsV2",
            space_id=user_space,
            message=survey_card,
            thread_id=thread_for_survey,
        )

    def get_post_call_survey_card(
        self,
        post_call_survey_questions: List[dict[str, List[str]]],
        thread_id: str,
        event: Optional[dict] = None,
    ) -> dict:
        """
        Create a post call survey card with the given questions and values

        Args:
            post_call_survey_questions (List[dict[str, List[str]]]): The questions and values for the survey

        Returns:
            dict: The survey card
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

        i = 0
        for question_dict in post_call_survey_questions:
            i += 1
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

    def create_card(self, llm_response) -> Dict:
        """
        Takes in the LLM response, extracts out any citations to the documents and adds them as reference links in the Google Chat card

        Args:
            llm_response: Response from LLM

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

        urls = re.findall(r"<ref>(http[s]?://[^>]+)</ref>", llm_response)

        processed_urls = []
        ref = 0

        for i, url in enumerate(urls):
            if url in processed_urls:
                continue

            if "gov.uk" in url:
                resource = "GOV UK"
            elif "citizensadvice.org.uk/advisernet" in url:
                resource = "Advisernet"
            elif "citizensadvice.org.uk" in url:
                resource = "Citizens Advice"

            ref = ref + 1
            llm_response = llm_response.replace(
                f"<ref>{url}</ref>", f'<a href="{url}">[{ref} - {resource}]</a>'
            )

            reference_link = {
                "textParagraph": {
                    "text": f'<a href="{url}">[{ref}- {resource}] {url}</a>'
                }
            }
            if reference_link not in reference_links_section["widgets"]:
                reference_links_section["widgets"].append(reference_link)

            processed_urls.append(url)

        llm_response_section = {
            "widgets": [
                {"textParagraph": {"text": llm_response}},
            ],
        }

        card["cardsV2"][0]["card"]["sections"].append(llm_response_section)
        card["cardsV2"][0]["card"]["sections"].append(reference_links_section)

        return card

    def send_message_to_supervisor_space(self, space_id, message):
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
        self, space_id: str, message: Dict, thread_id: str
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

    # Update message in the supervisor space
    def update_message_in_supervisor_space(
        self, space_id, message_id, new_message
    ):  # find message name
        self.supervisor.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            updateMask="cardsV2",
            body=new_message,
        ).execute()

    # Update message in the adviser space
    def update_dynamic_message_in_adviser_space(
        self, space_id, message_id, response_type, message
    ):
        self.caddy.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            updateMask=response_type,
            body=message,
        ).execute()

    # Delete message in the adviser space
    def delete_message_in_adviser_space(self, space_id, message_id):
        self.caddy.spaces().messages().delete(
            name=f"spaces/{space_id}/messages/{message_id}"
        ).execute()

    def create_supervision_request_card(
        self, user: str, initial_query: str
    ) -> Tuple[Dict, Dict, Dict, Dict, Dict]:
        """
        Creates supervision request status cards

        Args:
            user (str): email of user who has submitted a query
            initial_query (str): the user's query

        Returns:
            List[dict]: a list of the status cards
        """
        request_failed = self.responses.supervisor_request_failed(user, initial_query)

        request_processing = self.responses.supervisor_request_processing(
            user, initial_query
        )

        request_awaiting = self.responses.supervisor_request_pending(
            user, initial_query
        )

        request_approved = self.responses.supervisor_request_approved(
            user, initial_query
        )

        request_rejected = self.responses.supervisor_request_rejected(
            user, initial_query
        )

        return (
            request_failed,
            request_processing,
            request_awaiting,
            request_approved,
            request_rejected,
        )

    def create_supervision_card(
        self,
        user_email,
        event,
        new_request_message_id,
        request_approved,
        request_rejected,
        card_for_approval,
    ):
        conversation_id = event.conversation_id
        response_id = event.response_id
        message_id = event.message_id
        thread_id = event.thread_id

        approval_buttons_section = {
            "widgets": [
                {
                    "textInput": {
                        "label": "Supervisor Notes",
                        "type": "MULTIPLE_LINE",
                        "hintText": "Add approval notes or an override response for rejection",
                        "name": "supervisor_notes",
                    }
                },
                {
                    "buttonList": {
                        "buttons": [
                            {
                                "text": "👍",
                                "onClick": {
                                    "action": {
                                        "function": "Approved",
                                        "parameters": [
                                            {
                                                "key": "aiResponse",
                                                "value": json.dumps(card_for_approval),
                                            },
                                            {
                                                "key": "conversationId",
                                                "value": conversation_id,
                                            },
                                            {"key": "responseId", "value": response_id},
                                            {"key": "messageId", "value": message_id},
                                            {"key": "threadId", "value": thread_id},
                                            {
                                                "key": "newRequestId",
                                                "value": new_request_message_id,
                                            },
                                            {
                                                "key": "requestApproved",
                                                "value": json.dumps(request_approved),
                                            },
                                            {"key": "userEmail", "value": user_email},
                                        ],
                                    }
                                },
                            },
                            {
                                "text": "👎",
                                "onClick": {
                                    "action": {
                                        "function": "Rejected",
                                        "parameters": [
                                            {
                                                "key": "conversationId",
                                                "value": conversation_id,
                                            },
                                            {"key": "responseId", "value": response_id},
                                            {"key": "messageId", "value": message_id},
                                            {"key": "threadId", "value": thread_id},
                                            {
                                                "key": "newRequestId",
                                                "value": new_request_message_id,
                                            },
                                            {
                                                "key": "requestRejected",
                                                "value": json.dumps(request_rejected),
                                            },
                                            {"key": "userEmail", "value": user_email},
                                        ],
                                    }
                                },
                            },
                        ]
                    }
                },
            ],
        }

        card_for_approval_sections = deque(
            card_for_approval["cardsV2"][0]["card"]["sections"]
        )

        card_for_approval_sections.append(approval_buttons_section)

        card_for_approval_sections = list(card_for_approval_sections)

        card_for_approval["cardsV2"][0]["card"]["sections"] = card_for_approval_sections

        return card_for_approval

    def create_approved_card(
        self, card: dict, approver: str, supervisor_notes: str
    ) -> dict:
        """
        Takes a card and appends the supervisor approval section

        Args:
            Card: Google Card Card
            approver: the approver email
            supervisor_notes: supervisor approval notes

        Returns:
            Supervisor approved card
        """
        card["cardsV2"][0]["card"]["sections"].append(
            self.responses.approval_json_widget(approver, supervisor_notes)
        )

        return card

    def received_approval(self, event):
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

        domain = user_email.split("@")[1]
        _, office = enrolment.check_domain_status(domain)
        included_in_rct = enrolment.check_rct_status(office)
        if included_in_rct is True:
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
            supervisor_message=None,
        )

        return user_email, user_space, thread_id, approval_event

    def handle_supervisor_rejection(self, event) -> None:
        """
        Handle an incoming supervisor rejection from Google Chat

        Args:
            event: Google Chat Event

        Returns:
            None
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
        if included_in_rct is True:
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

        caddy.store_approver_event(rejection_event)

    def create_updated_supervision_card(
        self, supervision_card, approver, approved, supervisor_message
    ):
        if approved:
            approval_section = self.responses.approval_json_widget(
                approver, supervisor_notes=supervisor_message
            )
        else:
            approval_section = self.responses.rejection_json_widget(
                approver, supervisor_message
            )

        card_for_approval_sections = deque(
            supervision_card["cardsV2"][0]["card"]["sections"]
        )
        card_for_approval_sections.pop()  # remove thumbs up/ thumbs down section
        card_for_approval_sections.append(approval_section)

        card_for_approval_sections = list(card_for_approval_sections)

        supervision_card["cardsV2"][0]["card"]["sections"] = card_for_approval_sections

        return supervision_card

    def create_rejected_card(self, card, approver):
        rejection_json = self.responses.rejection_json_widget(approver)

        card["cardsV2"][0]["card"]["sections"].append(rejection_json)

        return card

    def user_list_dialog(self, supervision_users: str, space_display_name: str):
        list_dialog = {
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
        return list_dialog

    def failed_dialog(self, error):
        print(f"### FAILED: {error} ###")

    def add_user(self, event):
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]
        role = event["common"]["formInputs"]["role"]["stringInputs"]["value"][0]
        supervisor_space_id = event["space"]["name"].split("/")[1]

        try:
            enrolment.register_user(user, role, supervisor_space_id)
        except Exception as error:
            print(f"Adding user failed: {error}")

    def remove_user(self, event):
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]

        try:
            enrolment.remove_user(user)
        except Exception as error:
            print(f"Adding user failed: {error}")

    def list_space_users(self, event):
        supervision_space_id = event["space"]["name"].split("/")[1]
        space_name = event["space"]["displayName"]

        space_users = enrolment.list_users(supervision_space_id)

        return self.user_list_dialog(
            supervision_users=space_users, space_display_name=space_name
        )

    def get_survey_card(
        self, thread_id: str, user: str, event: Optional[dict] = None
    ) -> dict:
        """
        Gets a post call survey card for the given user

        Args:
            user (str): The email of the user

        Returns:
            dict: The survey card
        """
        post_call_survey_questions = get_survey(user)

        survey_card = self.get_post_call_survey_card(
            post_call_survey_questions, thread_id, event
        )

        return survey_card

    def call_complete_confirmation(
        self, user: str, user_space: str, thread_id: str
    ) -> None:
        """
        Send a card to the adviser space to confirm the call is complete

        Args:
            user (str): The email of the user
            user_space (str): The space ID of the user
            thread_id (str): The thread ID of the conversation

        Returns:
            None
        """
        survey_card = self.get_survey_card(thread_id, user)
        call_complete_card = self.responses.call_complete_card(survey_card)

        self.send_dynamic_to_adviser_space(
            response_type="cardsV2",
            space_id=user_space,
            message=call_complete_card,
            thread_id=thread_id,
        )

    def finalise_caddy_call(self, event) -> None:
        """
        Marks a call as complete and triggers post call survey upon user triggered event

        Args:
            Google Chat Event

        Returns:
            None
        """
        survey_card = json.loads(event["common"]["parameters"]["survey"])
        thread_id = event["message"]["thread"]["name"].split("/")[3]
        user_space = event["space"]["name"].split("/")[1]
        user = event["user"]["email"]
        caddy.mark_call_complete(user=user, thread_id=thread_id)
        survey_required = check_if_survey_required(user)
        if survey_required is True:
            self.update_survey_card_in_adviser_space(
                space_id=user_space,
                message_id=event["message"]["name"].split("/")[3],
                card=self.messages.CALL_COMPLETE,
            )
            self.run_survey(survey_card, user_space, thread_id)

    def handle_edited_query(self, event) -> CaddyMessageEvent:
        """
        Handles a edited query event from PII detected message

        Args:
            Google Chat Event

        Returns:
            CaddyMessageEvent
        """
        edited_message = event["common"]["formInputs"]["editedQuery"]["stringInputs"][
            "value"
        ][0]
        event = json.loads(event["common"]["parameters"]["message_event"])
        event["message"]["text"] = edited_message
        event["proceed"] = True
        caddy_message = self.format_message(event)
        return caddy_message

    def handle_proceed_query(self, event) -> CaddyMessageEvent:
        """
        Handles a proceed overwrite event from PII detected message

        Args:
            Google Chat Event

        Returns:
            CaddyMessageEvent
        """
        event = json.loads(event["common"]["parameters"]["message_event"])
        event["proceed"] = True
        return self.format_message(event)

    def handle_control_group_query(self, event) -> CaddyMessageEvent:
        """
        Handles a control group forward

        Args:
            Google Chat Event

        Returns:
            CaddyMessageEvent
        """
        message_event = event["common"]["parameters"]["message_event"]
        caddy_message_event = json.loads(message_event)
        return CaddyMessageEvent.model_validate(caddy_message_event)

    def handle_supervisor_approval(self, event):
        """
        Handles inbound Google Chat supervisor approvals

        Args:
            event: Google Chat Event

        Returns:
            None
        """
        (
            user,
            user_space,
            thread_id,
            approval_event,
        ) = self.received_approval(event)
        caddy.store_approver_event(approval_event)

    def continue_existing_interaction(self, event):
        """
        Updates the existing interaction card to reflect the chosen option of continue

        Args:
            event: google chat event

        Returns:
            None
        """
        self.update_survey_card_in_adviser_space(
            space_id=event["space"]["name"].split("/")[1],
            message_id=event["message"]["name"].split("/")[3],
            card=self.messages.CONTINUE_EXISTING_INTERACTION,
        )

    def end_existing_interaction(self, event):
        """
        Updates the existing interaction card to reflect the chosen option of end

        Args:
            event: google chat event

        Returns:
            None
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

    def append_survey_questions(
        self, card: dict, thread_id: dict, user: str, event: Optional[dict] = None
    ) -> dict:
        """
        Appends survey directly to response card for RCT users

        Args:
            card (dict): response card
            thread_id (str): the thread_id of the query
            user (str): the user who provided the query
            event (Optional[dict]): allows providing of an event for request continuation
        Returns:
            card (dict): returns the processed card with survey questions appended
        """
        survey_card = self.get_survey_card(thread_id, user, event)
        card["cardsV2"][0]["card"]["sections"].append(
            survey_card["cardsV2"][0]["card"]["sections"]
        )
        return card
