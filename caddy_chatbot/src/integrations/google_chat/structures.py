import os
import json
from datetime import datetime

from caddy_core.models import CaddyMessageEvent, ApprovalEvent
from caddy_core.services.anonymise import analyse
from caddy_core.services.survey import get_survey, check_if_survey_required
from caddy_core.services import enrolment
from caddy_core.utils.tables import evaluation_table
from caddy_core import core as caddy
from integrations.google_chat.content import MESSAGES
from integrations.google_chat import responses
from integrations.google_chat.auth import get_google_creds

from fastapi import status
from fastapi.responses import JSONResponse

from googleapiclient.discovery import build

from typing import List
from collections import deque


class GoogleChat:
    def __init__(self):
        self.client = "Google Chat"
        self.messages = MESSAGES
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
                    message=self.messages["pii_detected"],
                    message_event=event,
                )

                return "PII Detected"

        thread_id, message_id = self.send_message_to_adviser_space(
            space_id=space_id, thread_id=thread_id, message="*Status:* _*Processing*_"
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

    def send_message_to_adviser_space(self, space_id, thread_id, message):
        """
        Sends a message to the adviser space
        Returns the thread_id and message_id of the sent message
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

    def update_message_in_adviser_space(self, space_id: str, message_id: str, message):
        self.caddy.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            body=message,
            updateMask="text",
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
        question = event["common"]["parameters"]["question"]
        response = event["common"]["parameters"]["response"]
        threadId = event["message"]["thread"]["name"].split("/")[3]
        card = event["message"]["cardsV2"]
        spaceId = event["space"]["name"].split("/")[1]
        messageId = event["message"]["name"].split("/")[3]

        survey_response = [{question: response}]

        evaluation_entry = evaluation_table.get_item(Key={"threadId": str(threadId)})

        if "Item" in evaluation_entry and "surveyResponse" in evaluation_entry["Item"]:
            evaluation_table.update_item(
                Key={"threadId": str(threadId)},
                UpdateExpression="set surveyResponse = list_append(surveyResponse, :surveyResponse)",
                ExpressionAttributeValues={":surveyResponse": survey_response},
                ReturnValues="UPDATED_NEW",
            )
        else:
            evaluation_table.update_item(
                Key={"threadId": str(threadId)},
                UpdateExpression="set surveyResponse = :surveyResponse",
                ExpressionAttributeValues={":surveyResponse": survey_response},
                ReturnValues="UPDATED_NEW",
            )

        response_received = {
            "textParagraph": {
                "text": '<font color="#00ba01"><b>✅ survey response received</b></font>'
            }
        }

        for section in card[0]["card"]["sections"]:
            if section["widgets"][0]["textParagraph"]["text"] == question:
                del section["widgets"][1]["buttonList"]
                section["widgets"].append(response_received)

        self.update_survey_card_in_adviser_space(
            space_id=spaceId, message_id=messageId, card={"cardsV2": card}
        )

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
    ) -> None:
        """
        Sends a dynamic message to the adviser space given a type of response

        Args:
            response_type (str): The type of response to send
            space_id (str): The space ID of the user
            message (dict): The message to send
            thread_id (str): The thread ID of the conversation

        Returns:
            None
        """
        match response_type:
            case "text":
                self.caddy.spaces().messages().create(
                    parent=f"spaces/{space_id}",
                    body={
                        "text": message,
                        "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
                    },
                    messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
                ).execute()
            case "cardsV2":
                self.caddy.spaces().messages().create(
                    parent=f"spaces/{space_id}",
                    body={
                        "cardsV2": message["cardsV2"],
                        "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
                    },
                    messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
                ).execute()

    def run_new_survey(self, user: str, thread_id: str, user_space: str) -> None:
        """
        Run a survey in the adviser space by getting the survey questions and values by providing a user to the get_survey function

        Args:
            survey_card (dict): The survey card to run
            user_space (str): The space ID of the user
            thread_id (str): The thread ID of the conversation

        Returns:
            None
        """
        post_call_survey_questions, post_call_survey_values = get_survey(user)

        survey_card = self.get_post_call_survey_card(
            post_call_survey_questions, post_call_survey_values
        )

        self.send_dynamic_to_adviser_space(
            response_type="cardsV2",
            space_id=user_space,
            message=survey_card,
            thread_id=thread_id,
        )

    def get_post_call_survey_card(
        self, post_call_survey_questions: List[str], post_call_survey_values: List[str]
    ) -> dict:
        """
        Create a post call survey card with the given questions and values

        Args:
            post_call_survey_questions (List[str]): The questions for the survey
            post_call_survey_values (List[str]): The values for the survey

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

        for question in post_call_survey_questions:
            section = {"widgets": []}

            question_section = {"textParagraph": {"text": question}}

            button_section = {"buttonList": {"buttons": []}}

            for value in post_call_survey_values:
                button_section["buttonList"]["buttons"].append(
                    {
                        "text": value,
                        "onClick": {
                            "action": {
                                "function": "survey_response",
                                "parameters": [
                                    {"key": "question", "value": question},
                                    {"key": "response", "value": value},
                                ],
                            }
                        },
                    }
                )

            section["widgets"].append(question_section)
            section["widgets"].append(button_section)

            card["cardsV2"][0]["card"]["sections"].append(section)

        return card

    def create_card(self, llm_response, source_documents):
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

        llm_response_section = {
            "widgets": [
                {"textParagraph": {"text": llm_response.llm_answer}},
            ],
        }

        card["cardsV2"][0]["card"]["sections"].append(llm_response_section)

        reference_links_section = {"header": "Reference links", "widgets": []}

        for document in source_documents:
            reference_link = {
                "textParagraph": {
                    "text": f"<a href=\"{document.metadata['source_url']}\">{document.metadata['source_url']}</a>"
                }
            }
            if reference_link not in reference_links_section["widgets"]:
                reference_links_section["widgets"].append(reference_link)

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

    def respond_to_supervisor_thread(self, space_id, message, thread_id):
        self.supervisor.spaces().messages().create(
            parent=f"spaces/{space_id}",
            body={
                "cardsV2": message["cardsV2"],
                "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
            },
            messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
        ).execute()

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

    def create_supervision_request_card(self, user, initial_query):
        request_awaiting = {
            "cardsV2": [
                {
                    "cardId": "aiResponseCard",
                    "card": {
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "decoratedText": {
                                            "startIcon": {
                                                "iconUrl": "https://storage.googleapis.com/sort_assets/adviser_icon.png",
                                            },
                                            "text": '<b><font color="#004f88"><i>AWAITING RESPONSE APPROVAL</i></font></b>',
                                        },
                                    },
                                    {
                                        "textParagraph": {
                                            "text": f"<b>{user}:</b> <i>{initial_query}</i>",
                                        }
                                    },
                                ],
                            }
                        ],
                    },
                },
            ],
        }

        request_approved = {
            "cardsV2": [
                {
                    "cardId": "aiResponseCard",
                    "card": {
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "decoratedText": {
                                            "startIcon": {
                                                "iconUrl": "https://storage.googleapis.com/sort_assets/approved.png",
                                            },
                                            "text": '<b><font color="#00ba01"><i>APPROVED</i></font></b>',
                                        },
                                    },
                                    {
                                        "textParagraph": {
                                            "text": f"<b>{user}:</b> <i>{initial_query}</i>",
                                        }
                                    },
                                ],
                            }
                        ],
                    },
                },
            ],
        }

        request_rejected = {
            "cardsV2": [
                {
                    "cardId": "aiResponseCard",
                    "card": {
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "decoratedText": {
                                            "startIcon": {
                                                "iconUrl": "https://storage.googleapis.com/sort_assets/rejected_icon.png",
                                            },
                                            "text": '<b><font color="#ec0101"><i>RESPONSE REJECTED</i></font></b>',
                                        },
                                    },
                                    {
                                        "textParagraph": {
                                            "text": f"<b>{user}:</b> <i>{initial_query}</i>",
                                        }
                                    },
                                ],
                            }
                        ],
                    },
                },
            ],
        }

        return request_awaiting, request_approved, request_rejected

    def create_supervision_card(
        self,
        user_email,
        event,
        new_request_message_id,
        request_approved,
        request_rejected,
    ):
        card_for_approval = event.llm_response_json
        conversation_id = event.conversation_id
        response_id = event.response_id
        message_id = event.message_id
        thread_id = event.thread_id

        approval_buttons_section = {
            "widgets": [
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
                                        "function": "rejected_dialog",
                                        "interaction": "OPEN_DIALOG",
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
                }
            ],
        }

        card_for_approval_sections = deque(
            card_for_approval["cardsV2"][0]["card"]["sections"]
        )

        card_for_approval_sections.append(approval_buttons_section)

        card_for_approval_sections = list(card_for_approval_sections)

        card_for_approval["cardsV2"][0]["card"]["sections"] = card_for_approval_sections

        return card_for_approval

    def handle_new_supervision_event(self, user, supervisor_space, event):
        (
            request_awaiting,
            request_approved,
            request_rejected,
        ) = self.create_supervision_request_card(
            user=user, initial_query=event.llmPrompt
        )
        (
            new_request_thread,
            new_request_message_id,
        ) = self.send_message_to_supervisor_space(
            space_id=supervisor_space, message=request_awaiting
        )

        card = self.create_supervision_card(
            user_email=user,
            event=event,
            new_request_message_id=new_request_message_id,
            request_approved=request_approved,
            request_rejected=request_rejected,
        )

        self.respond_to_supervisor_thread(
            space_id=supervisor_space, message=card, thread_id=new_request_thread
        )

    def create_approved_card(self, card, approver):
        approval_json = {
            "widgets": [
                {
                    "textParagraph": {
                        "text": f'<font color="#00ba01"><b>✅ Response approved by {approver}</b></font>'
                    }
                },
            ],
        }

        card["cardsV2"][0]["card"]["sections"].append(approval_json)

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

        approved_card = self.create_approved_card(card=card, approver=approver)

        updated_supervision_card = self.create_updated_supervision_card(
            supervision_card=supervisor_card,
            approver=approver,
            approved=True,
            supervisor_message="",
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

        self.update_dynamic_message_in_adviser_space(
            space_id=user_space,
            message_id=user_message_id,
            response_type="text",
            message={"text": "*Status:* _*Completed*_"},
        )

        self.update_dynamic_message_in_adviser_space(
            space_id=user_space,
            message_id=user_message_id,
            response_type="cardsV2",
            message=approved_card,
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

    def received_rejection(self, event):
        supervisor_card = {"cardsV2": event["message"]["cardsV2"]}
        user_space = event["common"]["parameters"]["conversationId"]
        approver = event["user"]["email"]
        response_id = event["common"]["parameters"]["responseId"]
        supervisor_space = event["space"]["name"].split("/")[1]
        message_id = event["message"]["name"].split("/")[3]
        user_message_id = event["common"]["parameters"]["messageId"]
        supervisor_message = event["common"]["formInputs"]["supervisorResponse"][
            "stringInputs"
        ]["value"][0]
        thread_id = event["common"]["parameters"]["threadId"]
        request_message_id = event["common"]["parameters"]["newRequestId"]
        request_card = json.loads(event["common"]["parameters"]["requestRejected"])
        user_email = event["common"]["parameters"]["userEmail"]

        self.update_message_in_supervisor_space(
            space_id=supervisor_space,
            message_id=request_message_id,
            new_message=request_card,
        )

        self.update_dynamic_message_in_adviser_space(
            space_id=user_space,
            message_id=user_message_id,
            response_type="text",
            message={"text": f"*Status:* _*AI response rejected by {approver}*_"},
        )

        self.send_dynamic_to_adviser_space(
            response_type="text",
            space_id=user_space,
            thread_id=thread_id,
            message=f"*{approver} says:* \n\n {supervisor_message}",
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

        return (
            self.responses.SUCCESS_DIALOG,
            user_email,
            user_space,
            thread_id,
            rejection_event,
        )

    def create_updated_supervision_card(
        self, supervision_card, approver, approved, supervisor_message
    ):
        if approved:
            approval_section = {
                "widgets": [
                    {
                        "textParagraph": {
                            "text": f'<font color="#00ba01"><b>✅ Response approved by {approver}</b></font>'
                        }
                    },
                ],
            }
        else:
            approval_section = {
                "widgets": [
                    {
                        "textParagraph": {
                            "text": f'<font color="#ec0101"><b>❌ Response rejected by {approver}.</b></font> \n\n <font color="#004F88"><i><b>Supervisor response:</b> {supervisor_message}</i></font>'
                        }
                    },
                ],
            }

        card_for_approval_sections = deque(
            supervision_card["cardsV2"][0]["card"]["sections"]
        )
        card_for_approval_sections.pop()  # remove thumbs up/ thumbs down section
        card_for_approval_sections.append(approval_section)

        card_for_approval_sections = list(card_for_approval_sections)

        supervision_card["cardsV2"][0]["card"]["sections"] = card_for_approval_sections

        return supervision_card

    def create_rejected_card(self, card, approver):
        rejection_json = {
            "widgets": [
                {
                    "textParagraph": {
                        "text": f'<font color="#ec0101"><b>❌ Response rejected by {approver}.</b> Please await supervisor response.</font>'
                    }
                },
            ],
        }

        card["cardsV2"][0]["card"]["sections"].append(rejection_json)

        return card

    def get_user_to_add_details_dialog(self):
        input_dialog = {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {
                    "dialog": {
                        "body": {
                            "sections": [
                                {
                                    "header": "Onboard a new user to Caddy",
                                    "widgets": [
                                        {
                                            "textParagraph": {
                                                "text": "To allow a new user to join Caddy within your organisation register their email below and select their permissions"
                                            }
                                        },
                                        {
                                            "textInput": {
                                                "label": "Email",
                                                "type": "SINGLE_LINE",
                                                "name": "email",
                                            }
                                        },
                                        {
                                            "selectionInput": {
                                                "type": "RADIO_BUTTON",
                                                "label": "Role",
                                                "name": "role",
                                                "items": [
                                                    {
                                                        "text": "Adviser",
                                                        "value": "Adviser",
                                                        "selected": True,
                                                    },
                                                    {
                                                        "text": "Supervisor",
                                                        "value": "Supervisor",
                                                        "selected": False,
                                                    },
                                                ],
                                            }
                                        },
                                        {
                                            "buttonList": {
                                                "buttons": [
                                                    {
                                                        "text": "Add User",
                                                        "onClick": {
                                                            "action": {
                                                                "function": "receiveDialog"
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
        return input_dialog

    def get_user_to_remove_details_dialog(self):
        input_dialog = {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {
                    "dialog": {
                        "body": {
                            "sections": [
                                {
                                    "header": "Remove a user from Caddy",
                                    "widgets": [
                                        {
                                            "textParagraph": {
                                                "text": "Input the email of the user whos access to Caddy supervision within your organisation you would like to revoke"
                                            }
                                        },
                                        {
                                            "textInput": {
                                                "label": "Email",
                                                "type": "SINGLE_LINE",
                                                "name": "email",
                                            }
                                        },
                                        {
                                            "buttonList": {
                                                "buttons": [
                                                    {
                                                        "text": "Remove User",
                                                        "onClick": {
                                                            "action": {
                                                                "function": "receiveDialog"
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
        return input_dialog

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

    def helper_dialog(self):
        helper_dialog = {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {
                    "dialog": {
                        "body": {
                            "sections": [
                                {
                                    "header": "Helper dialog for Caddy Supervisor",
                                    "widgets": [
                                        {
                                            "textParagraph": {
                                                "text": "Adding a New User:\n\nTo add a new user under your supervision space, use the command /addUser.\nExample: /addUser\n\nRemoving User Access:\n\nIf you need to revoke access for a user, use the /removeUser command.\nExample: /removeUser\n\nListing Registered Users:\n\nTo view a list of users currently registered under your supervision, use the /listUsers command.\nThis command will display a comprehensive list, making it easy to manage and monitor user access.\nExample: /listUsers"
                                            }
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                },
            }
        }
        return helper_dialog

    def failed_dialog(self, error):
        print(f"### FAILED: {error} ###")

    def get_supervisor_response_dialog(
        self,
        conversation_id,
        response_id,
        message_id,
        thread_id,
        new_request_message_id,
        request_rejected,
        user_email,
    ):
        supervisor_response_dialog = {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {
                    "dialog": {
                        "body": {
                            "sections": [
                                {
                                    "header": "Rejected response follow up",
                                    "widgets": [
                                        {
                                            "textInput": {
                                                "label": "Enter a valid response for the adviser to their question",
                                                "type": "MULTIPLE_LINE",
                                                "name": "supervisorResponse",
                                            }
                                        },
                                        {
                                            "buttonList": {
                                                "buttons": [
                                                    {
                                                        "text": "Submit response",
                                                        "onClick": {
                                                            "action": {
                                                                "function": "receiveSupervisorResponse",
                                                                "parameters": [
                                                                    {
                                                                        "key": "conversationId",
                                                                        "value": conversation_id,
                                                                    },
                                                                    {
                                                                        "key": "responseId",
                                                                        "value": response_id,
                                                                    },
                                                                    {
                                                                        "key": "messageId",
                                                                        "value": message_id,
                                                                    },
                                                                    {
                                                                        "key": "threadId",
                                                                        "value": thread_id,
                                                                    },
                                                                    {
                                                                        "key": "newRequestId",
                                                                        "value": new_request_message_id,
                                                                    },
                                                                    {
                                                                        "key": "requestRejected",
                                                                        "value": request_rejected,
                                                                    },
                                                                    {
                                                                        "key": "userEmail",
                                                                        "value": user_email,
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
        return supervisor_response_dialog

    def get_user_details(self, type: str):
        match type:
            case "Add":
                return self.get_user_to_add_details_dialog()
            case "Remove":
                return self.get_user_to_remove_details_dialog()

    def get_supervisor_response(self, event):
        conversation_id = event["common"]["parameters"]["conversationId"]
        response_id = event["common"]["parameters"]["responseId"]
        message_id = event["common"]["parameters"]["messageId"]
        thread_id = event["common"]["parameters"]["threadId"]
        new_request_message_id = event["common"]["parameters"]["newRequestId"]
        request_rejected = event["common"]["parameters"]["requestRejected"]
        user_email = event["common"]["parameters"]["userEmail"]

        return self.get_supervisor_response_dialog(
            conversation_id,
            response_id,
            message_id,
            thread_id,
            new_request_message_id,
            request_rejected,
            user_email,
        )

    def add_user(self, event):
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]
        role = event["common"]["formInputs"]["role"]["stringInputs"]["value"][0]
        supervisor_space_id = event["space"]["name"].split("/")[1]

        try:
            enrolment.register_user(user, role, supervisor_space_id)
            return self.responses.SUCCESS_DIALOG
        except Exception as error:
            return self.failed_dialog(error)

    def remove_user(self, event):
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]

        try:
            enrolment.remove_user(user)
            return self.responses.SUCCESS_DIALOG
        except Exception as error:
            return self.failed_dialog(error)

    def list_space_users(self, event):
        supervision_space_id = event["space"]["name"].split("/")[1]
        space_name = event["space"]["displayName"]

        space_users = enrolment.list_users(supervision_space_id)

        return self.user_list_dialog(
            supervision_users=space_users, space_display_name=space_name
        )

    def get_survey(self, user: str) -> dict:
        """
        Gets a post call survey card for the given user

        Args:
            user (str): The email of the user

        Returns:
            dict: The survey card
        """
        post_call_survey_questions, post_call_survey_values = get_survey(user)

        survey_card = self.get_post_call_survey_card(
            post_call_survey_questions, post_call_survey_values
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
        survey_card = self.get_survey(user)
        call_complete_card = {
            "cardsV2": [
                {
                    "cardId": "callCompleteCard",
                    "card": {
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "buttonList": {
                                            "buttons": [
                                                {
                                                    "text": "Mark call complete",
                                                    "onClick": {
                                                        "action": {
                                                            "function": "call_complete",
                                                            "parameters": [
                                                                {
                                                                    "key": "survey",
                                                                    "value": json.dumps(
                                                                        survey_card
                                                                    ),
                                                                },
                                                            ],
                                                        }
                                                    },
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        ],
                    },
                },
            ],
        }

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
        caddy.mark_call_complete(thread_id)
        survey_required = check_if_survey_required(event["user"]["email"])
        if survey_required is True:
            self.update_survey_card_in_adviser_space(
                space_id=user_space,
                message_id=event["message"]["name"].split("/")[3],
                card={
                    "cardsV2": [
                        {
                            "cardId": "callCompleteConfirmed",
                            "card": {
                                "sections": [
                                    {
                                        "widgets": [
                                            {
                                                "textParagraph": {
                                                    "text": '<font color="#00ba01"><b>📞 Call complete, please complete the post call survey below</b></font>'
                                                }
                                            },
                                        ],
                                    },
                                ],
                            },
                        },
                    ],
                },
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
