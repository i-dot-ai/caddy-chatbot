from collections import deque
import json
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()


@xray_recorder.capture()
def create_supervision_request_card(user_identifier, initial_query):
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
                                        "text": f"<b>{user_identifier}:</b> <i>{initial_query}</i>",
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
                                        "text": f"<b>{user_identifier}:</b> <i>{initial_query}</i>",
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
                                        "text": f"<b>{user_identifier}:</b> <i>{initial_query}</i>",
                                    }
                                },
                            ],
                        }
                    ],
                },
            },
        ],
    }

    print(request_awaiting)
    print(request_approved)
    print(request_rejected)

    return request_awaiting, request_approved, request_rejected


@xray_recorder.capture()
def create_supervision_card(
    card_for_approval,
    conversation_id,
    response_id,
    message_id,
    thread_id,
    new_request_message_id,
    request_approved,
    request_rejected,
    user_email,
):
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


@xray_recorder.capture()
def create_updated_supervision_card(
    supervision_card, approver, approved, supervisor_message
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
def create_approved_card(card, approver):
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
def create_rejected_card(card, approver):
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
def get_user_to_add_details_dialog():
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
def get_user_to_remove_details_dialog():
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
def user_list_dialog(supervision_users: str, space_display_name: str):
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
def helper_dialog():
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
def success_dialog():
    success_dialog = {
        "action_response": {"type": "DIALOG", "dialog_action": {"action_status": "OK"}}
    }
    return success_dialog


@xray_recorder.capture()
def failed_dialog(error):
    print(f"### FAILED: {error} ###")


@xray_recorder.capture()
def get_supervisor_response_dialog(
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
