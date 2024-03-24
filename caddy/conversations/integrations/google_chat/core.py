import json

from caddy.models.core import CaddyMessageEvent
from caddy.services.anonymise import analyse
from caddy.utils.tables import evaluation_table
from integrations.google_chat.content import MESSAGES
from integrations.google_chat.auth import get_google_creds

from googleapiclient.discovery import build

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()


class GoogleChat:
    def __init__(self):
        self.client = "Google Chat"
        self.messages = MESSAGES
        self.caddy = build("chat", "v1", credentials=get_google_creds("CaddyCred"))

    @xray_recorder.capture()
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

    @xray_recorder.capture()
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

    @xray_recorder.capture()
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

    @xray_recorder.capture()
    def update_message_in_adviser_space(self, space_id: str, message_id: str, message):
        self.caddy.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            body=message,
            updateMask="text",
        ).execute()

    @xray_recorder.capture()
    def update_survey_card_in_adviser_space(self, space_id: str, message_id: str, card):
        self.caddy.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            body=card,
            updateMask="cardsV2",
        ).execute()

    @xray_recorder.capture()
    def get_edit_query_dialog(self, event):
        event = json.loads(event["common"]["parameters"]["message_event"])
        message_string = event["message"]["text"]
        message_string = message_string.replace("@Caddy", "")

        return self.edit_query_dialog(event, message_string)

    @xray_recorder.capture()
    def handle_survey_response(self, event):
        card = event["message"]["cardsV2"]
        question = event["common"]["parameters"]["question"]
        response = event["common"]["parameters"]["response"]
        threadId = event["message"]["thread"]["name"].split("/")[3]
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

    def success_dialog(self):
        success_dialog = {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {"action_status": "OK"},
            }
        }
        return success_dialog

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
