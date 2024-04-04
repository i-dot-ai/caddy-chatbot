import os
from collections import deque
import json
from datetime import datetime

from googleapiclient.discovery import build
from integrations.google_chat.auth import get_google_creds
from integrations.google_chat.content import MESSAGES

from caddy.models.core import ApprovalEvent
from caddy.services import enrolment
from caddy.services.survey import get_survey

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()


class GoogleChat:
    def __init__(self):
        self.client = "Google Chat"
        self.messages = MESSAGES
        self.caddy = build(
            "chat",
            "v1",
            credentials=get_google_creds(os.getenv("CADDY_SERVICE_ACCOUNT_ID")),
        )
        self.supervisor = build(
            "chat",
            "v1",
            credentials=get_google_creds(
                os.getenv("CADDY_SUPERVISOR_SERVICE_ACCOUNT_ID")
            ),
        )

    @xray_recorder.capture()
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

    @xray_recorder.capture()
    def respond_to_supervisor_thread(self, space_id, message, thread_id):
        self.supervisor.spaces().messages().create(
            parent=f"spaces/{space_id}",
            body={
                "cardsV2": message["cardsV2"],
                "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
            },
            messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
        ).execute()

    # Send message to the adviser space
    @xray_recorder.capture()
    def send_message_to_adviser_space(
        self, response_type, space_id, message, thread_id
    ):
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

    # Update message in the supervisor space
    @xray_recorder.capture()
    def update_message_in_supervisor_space(
        self, space_id, message_id, new_message
    ):  # find message name
        self.supervisor.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            updateMask="cardsV2",
            body=new_message,
        ).execute()

    # Update message in the adviser space
    @xray_recorder.capture()
    def update_message_in_adviser_space(
        self, space_id, message_id, response_type, message
    ):
        self.caddy.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            updateMask=response_type,
            body=message,
        ).execute()

    # Delete message in the adviser space
    @xray_recorder.capture()
    def delete_message_in_adviser_space(self, space_id, message_id):
        self.caddy.spaces().messages().delete(
            name=f"spaces/{space_id}/messages/{message_id}"
        ).execute()

    @xray_recorder.capture()
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

    @xray_recorder.capture()
    def create_supervision_card(
        self,
        user_email,
        event,
        new_request_message_id,
        request_approved,
        request_rejected,
    ):
        card_for_approval = event["llm_response_json"]
        conversation_id = event["conversation_id"]
        response_id = event["response_id"]
        message_id = event["message_id"]
        thread_id = event["thread_id"]

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
            user=user, initial_query=event["llmPrompt"]
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

    @xray_recorder.capture()
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

    @xray_recorder.capture()
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

        self.update_message_in_adviser_space(
            space_id=user_space,
            message_id=user_message_id,
            response_type="text",
            message={"text": "*Status:* _*Completed*_"},
        )

        self.update_message_in_adviser_space(
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

    @xray_recorder.capture()
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

        self.update_message_in_adviser_space(
            space_id=user_space,
            message_id=user_message_id,
            response_type="text",
            message={"text": f"*Status:* _*AI response rejected by {approver}*_"},
        )

        self.send_message_to_adviser_space(
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

        return self.success_dialog(), user_email, user_space, thread_id, rejection_event

    @xray_recorder.capture()
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

    @xray_recorder.capture()
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

    @xray_recorder.capture()
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

    @xray_recorder.capture()
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

    @xray_recorder.capture()
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

    @xray_recorder.capture()
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

    @xray_recorder.capture()
    def success_dialog(self):
        success_dialog = {
            "action_response": {
                "type": "DIALOG",
                "dialog_action": {"action_status": "OK"},
            }
        }
        return success_dialog

    @xray_recorder.capture()
    def failed_dialog(self, error):
        print(f"### FAILED: {error} ###")

    @xray_recorder.capture()
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

    @xray_recorder.capture()
    def get_user_details(self, type: str):
        match type:
            case "Add":
                return self.get_user_to_add_details_dialog()
            case "Remove":
                return self.get_user_to_remove_details_dialog()

    @xray_recorder.capture()
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

    @xray_recorder.capture()
    def add_user(self, event):
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]
        role = event["common"]["formInputs"]["role"]["stringInputs"]["value"][0]
        supervisor_space_id = event["space"]["name"].split("/")[1]

        try:
            enrolment.register_user(user, role, supervisor_space_id)
            return self.success_dialog()
        except Exception as error:
            return self.failed_dialog(error)

    @xray_recorder.capture()
    def remove_user(self, event):
        user = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]

        try:
            enrolment.remove_user(user)
            return self.success_dialog()
        except Exception as error:
            return self.failed_dialog(error)

    @xray_recorder.capture()
    def list_space_users(self, event):
        supervision_space_id = event["space"]["name"].split("/")[1]
        space_name = event["space"]["displayName"]

        space_users = enrolment.list_users(supervision_space_id)

        return self.user_list_dialog(
            supervision_users=space_users, space_display_name=space_name
        )

    @xray_recorder.capture()
    def get_post_call_survey_card(
        self, post_call_survey_questions, post_call_survey_values
    ):
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

    @xray_recorder.capture()
    def run_survey(self, user, user_space, thread_id):
        post_call_survey_questions, post_call_survey_values = get_survey(user)

        survey_card = self.get_post_call_survey_card(
            post_call_survey_questions, post_call_survey_values
        )

        self.send_message_to_adviser_space(
            response_type="cardsV2",
            space_id=user_space,
            message=survey_card,
            thread_id=thread_id,
        )
