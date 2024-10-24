from fastapi import status
from fastapi.responses import JSONResponse, Response
from integrations.google_chat import content
from caddy_core.models import LLMOutput, UserMessage, SupervisionEvent
from typing import Dict, Any, Optional
import re
import json

# --- Status Responses --- #
NO_CONTENT = Response(status_code=status.HTTP_204_NO_CONTENT)
ACCEPTED = Response(status_code=status.HTTP_202_ACCEPTED)

# --- Text Responses --- #
DOMAIN_NOT_ENROLLED = JSONResponse(
    status_code=status.HTTP_200_OK,
    content=content.DOMAIN_NOT_ENROLLED,
)

USER_NOT_ENROLLED = JSONResponse(
    status_code=status.HTTP_200_OK,
    content=content.USER_NOT_ENROLLED,
)

USER_NOT_SUPERVISOR = JSONResponse(
    status_code=status.HTTP_200_OK,
    content=content.USER_NOT_SUPERVISOR,
)

INTRODUCE_CADDY_IN_DM = JSONResponse(
    status_code=status.HTTP_200_OK, content=content.INTRODUCE_CADDY_DM_CARD
)

INTRODUCE_CADDY_SUPERVISOR_IN_DM = JSONResponse(
    status_code=status.HTTP_200_OK,
    content=content.INTRODUCE_CADDY_SUPERVISOR_IN_DM,
)


def introduce_caddy_in_space(space_name: str) -> JSONResponse:
    """
    Creates an introduction card with space name and returns via JSONResponse

    Args:
        space_name (str): name of space

    Returns:
        JSONResponse of card
    """
    card = {
        "cardsV2": [
            {
                "cardId": "IntroductionCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "columns": {
                                        "columnItems": [
                                            {
                                                "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                                                "horizontalAlignment": "CENTER",
                                                "verticalAlignment": "CENTER",
                                                "widgets": [
                                                    {
                                                        "textParagraph": {
                                                            "text": content.INTRODUCE_CADDY_IN_SPACE.format(
                                                                space_name=space_name
                                                            )
                                                        }
                                                    },
                                                    {
                                                        "decoratedText": {
                                                            "icon": {
                                                                "materialIcon": {
                                                                    "name": "priority_high"
                                                                }
                                                            },
                                                            "topLabel": "Getting started",
                                                            "text": "<b>@Caddy</b> if you would like my help.",
                                                        }
                                                    },
                                                ],
                                            },
                                            {
                                                "widgets": [
                                                    {
                                                        "image": {
                                                            "imageUrl": "https://ai.gov.uk/img/caddy1.webp",
                                                            "altText": "Caddy, an owl icon",
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    }
                                },
                            ],
                        }
                    ]
                },
            }
        ]
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=card,
    )


def introduce_caddy_supervisor_in_space(space_name: str) -> JSONResponse:
    """
    Introduces Caddy Supervisor in a space

    Args:
        space_name (str): name of space

    Returns:
        JSONResponse of card
    """
    card = {
        "cardsV2": [
            {
                "cardId": "IntroductionCaddy",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "columns": {
                                        "columnItems": [
                                            {
                                                "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                                                "horizontalAlignment": "CENTER",
                                                "verticalAlignment": "CENTER",
                                                "widgets": [
                                                    {
                                                        "textParagraph": {
                                                            "text": f"Hi, I'm Caddy's supervisor companion! Thank you for adding me to {space_name} \n\n Caddy is an AI powered co-pilot for Citizens Advice advisers using content from the below:"
                                                        }
                                                    },
                                                    {
                                                        "decoratedText": {
                                                            "icon": {
                                                                "materialIcon": {
                                                                    "name": "web"
                                                                }
                                                            },
                                                            "text": "Citizens Advice",
                                                        }
                                                    },
                                                    {
                                                        "decoratedText": {
                                                            "icon": {
                                                                "materialIcon": {
                                                                    "name": "web"
                                                                }
                                                            },
                                                            "text": "Advisernet",
                                                        }
                                                    },
                                                    {
                                                        "decoratedText": {
                                                            "icon": {
                                                                "materialIcon": {
                                                                    "name": "web"
                                                                }
                                                            },
                                                            "text": "GOV.UK",
                                                        }
                                                    },
                                                    {
                                                        "textParagraph": {
                                                            "text": "To get started you will need to register the advisers into your supervision space so their messages come to you."
                                                        }
                                                    },
                                                    {
                                                        "decoratedText": {
                                                            "icon": {
                                                                "materialIcon": {
                                                                    "name": "person_add"
                                                                }
                                                            },
                                                            "topLabel": "Register an adviser",
                                                            "text": "<b>/addUser</b>",
                                                        }
                                                    },
                                                    {
                                                        "decoratedText": {
                                                            "icon": {
                                                                "materialIcon": {
                                                                    "name": "help"
                                                                }
                                                            },
                                                            "topLabel": "Other commands",
                                                            "text": "<b>/help</b>",
                                                        }
                                                    },
                                                ],
                                            },
                                            {
                                                "widgets": [
                                                    {
                                                        "image": {
                                                            "imageUrl": "https://ai.gov.uk/img/caddy1.webp",
                                                            "altText": "Caddy, an owl icon",
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    }
                                }
                            ]
                        }
                    ]
                },
            }
        ]
    }
    return JSONResponse(status_code=status.HTTP_200_OK, content=card)


def existing_call_reminder(
    event, space_id, thread_id, call_start_time, survey_thread_id
):
    """
    Existing call reminder
    """
    existing_call_reminder_card = {
        "cardsV2": [
            {
                "cardId": "survey_reminder",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": content.EXISTING_CALL_REMINDER.format(
                                            call_start_time=call_start_time
                                        )
                                    }
                                },
                            ],
                        },
                        {
                            "widgets": [
                                {
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "New Interaction",
                                                "onClick": {
                                                    "action": {
                                                        "function": "end_existing_interaction",
                                                        "parameters": [
                                                            {
                                                                "key": "message_event",
                                                                "value": json.dumps(
                                                                    event
                                                                ),
                                                            },
                                                            {
                                                                "key": "thread_id",
                                                                "value": survey_thread_id,
                                                            },
                                                        ],
                                                    }
                                                },
                                            },
                                            {
                                                "text": "Continue Existing Interaction",
                                                "onClick": {
                                                    "action": {
                                                        "function": "continue_existing_interaction",
                                                        "parameters": [
                                                            {
                                                                "key": "message_event",
                                                                "value": json.dumps(
                                                                    event
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
    }
    return existing_call_reminder_card


# --- Card Responses --- #

# TODO Add clean card responses


def supervisor_rejection(approver: str, supervisor_message: str) -> dict:
    """
    A function to return a formatted supervisor rejection card

    Args:
        approver (str): the supervisor who has performed the rejection
        supervisor_message (str): the supervisors rejection message

    Returns:
        card (dict)
    """
    card = {
        "cardsV2": [
            {
                "cardId": "StatusCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {"materialIcon": {"name": "block"}},
                                        "text": '<font color="#ec0101"><b>Response rejected</b></font>',
                                        "bottomLabel": f"by {approver}",
                                    }
                                },
                            ]
                        }
                    ]
                },
            },
        ],
    }

    if supervisor_message != "":
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        supervisor_message = re.sub(
            url_pattern, r'<a href="\g<0>">\g<0></a>', supervisor_message
        )
        card["cardsV2"][0]["card"]["sections"][0]["widgets"].append({"divider": {}})
        card["cardsV2"][0]["card"]["sections"][0]["widgets"].append(
            {
                "decoratedText": {
                    "topLabel": "Supervisor Notes",
                }
            }
        )
        card["cardsV2"][0]["card"]["sections"][0]["widgets"].append(
            {"textParagraph": {"text": supervisor_message}}
        )

    return card


def control_group_selection(control_group_message, caddy_message) -> dict:
    """
    Formats a control group message into a control group selection response card

    Args:
        control_group_message (str): message for control group selectees
    Return:
        card (dict)
    """
    card = {
        "cardsV2": [
            {
                "cardId": "controlGroupCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {
                                            "materialIcon": {"name": "query_stats"}
                                        },
                                        "topLabel": "control group selection",
                                    }
                                },
                                {"textParagraph": {"text": control_group_message}},
                                {
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "I still need help, forward query to supervisor, then complete survey",
                                                "onClick": {
                                                    "action": {
                                                        "function": "handle_control_group_forward",
                                                        "parameters": [
                                                            {
                                                                "key": "message_event",
                                                                "value": caddy_message.model_dump_json(),
                                                            },
                                                        ],
                                                    }
                                                },
                                            },
                                            {
                                                "text": "I no longer need help. Complete survey",
                                                "onClick": {
                                                    "action": {
                                                        "function": "control_group_survey",
                                                        "parameters": [
                                                            {
                                                                "key": "message_event",
                                                                "value": caddy_message.model_dump_json(),
                                                            },
                                                        ],
                                                    }
                                                },
                                            },
                                        ]
                                    }
                                },
                            ]
                        }
                    ]
                },
            },
        ],
    }
    return card


def approval_json_widget(approver: str, supervisor_notes: str) -> dict:
    """
    This takes in an approver and generates the approved response widget

    Args:
        approver (str): the approver of the message
        supervisor_notes (str): supervisor approval notes

    Response:
        widget (dict)
    """
    widget = {
        "widgets": [
            {
                "decoratedText": {
                    "icon": {"materialIcon": {"name": "verified"}},
                    "text": '<font color="#00ba01"><b>Response approved</b></font>',
                    "bottomLabel": f"by {approver}",
                },
            }
        ]
    }

    if supervisor_notes != "":
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        supervisor_notes = re.sub(
            url_pattern, r'<a href="\g<0>">\g<0></a>', supervisor_notes
        )
        widget["widgets"].append({"divider": {}})
        widget["widgets"].append(
            {
                "decoratedText": {
                    "topLabel": "Supervisor Notes",
                }
            }
        )
        widget["widgets"].append({"textParagraph": {"text": supervisor_notes}})

    return widget


def supervisor_request_rejected(user: str, initial_query: str) -> dict:
    """
    Creates a supervisor request rejected card

    Args:
        user (str): user who submitted the query
        initial_query: query of the user

    Returns:
        card (dict)
    """
    card = {
        "cardsV2": [
            {
                "cardId": "aiResponseCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {"materialIcon": {"name": "block"}},
                                        "text": '<b><font color="#ec0101">RESPONSE REJECTED</font></b>',
                                    }
                                },
                                {
                                    "textParagraph": {
                                        "text": initial_query,
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "bottomLabel": user,
                                    }
                                },
                            ]
                        }
                    ],
                },
            },
        ],
    }
    return card


def message_control_forward(user: str, query: str) -> dict:
    """
    Creates a supervisor request forward card

    Args:
        user (str): user who submitted the query
        initial_query: query of the user

    Returns:
        card (dict)
    """
    card = {
        "cardsV2": [
            {
                "cardId": "requestForward",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {"materialIcon": {"name": "help"}},
                                        "text": '<b><font color="#006278">Supervisor support required</font></b>',
                                    }
                                },
                                {
                                    "textParagraph": {
                                        "text": query,
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "bottomLabel": user,
                                    }
                                },
                            ]
                        }
                    ],
                },
            },
        ],
    }
    return card


def supervisor_request_approved(user: str, initial_query: str) -> dict:
    """
    Creates a supervisor request approved card

    Args:
        user (str): user who submitted the query
        initial_query: query of the user

    Returns:
        card (dict)
    """
    card = {
        "cardsV2": [
            {
                "cardId": "aiResponseCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {"materialIcon": {"name": "verified"}},
                                        "text": '<b><font color="#00ba01">RESPONSE APPROVED</font></b>',
                                    }
                                },
                                {
                                    "textParagraph": {
                                        "text": initial_query,
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "bottomLabel": user,
                                    }
                                },
                            ]
                        }
                    ],
                },
            },
        ],
    }
    return card


def supervisor_request_processing(user: str, initial_query: str) -> dict:
    """
    Creates a supervisor request processing card

    Args:
        user (str): user who submitted the query
        initial_query: query of the user

    Returns:
        card (dict)
    """
    card = {
        "cardsV2": [
            {
                "cardId": "statusCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {
                                            "materialIcon": {
                                                "name": "quick_reference_all"
                                            }
                                        },
                                        "text": '<b><font color="#171738">CADDY PROCESSING</font></b>',
                                    }
                                },
                                {
                                    "textParagraph": {
                                        "text": initial_query,
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "bottomLabel": user,
                                    }
                                },
                            ]
                        }
                    ],
                },
            },
        ],
    }
    return card


def supervisor_request_follow_up_details(user: str, initial_query: str) -> dict:
    """
    Creates a supervisor request awaiting follow up details card

    Args:
        user (str): user who submitted the query
        initial_query: query of the user

    Returns:
        card (dict)
    """
    card = {
        "cardsV2": [
            {
                "cardId": "aiResponseCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {
                                            "materialIcon": {"name": "psychology"}
                                        },
                                        "text": '<b><font color="#171738">CADDY AWAITING ADVISER FOLLOW UP</font></b>',
                                    }
                                },
                                {
                                    "textParagraph": {
                                        "text": initial_query,
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "bottomLabel": user,
                                    }
                                },
                            ]
                        }
                    ],
                },
            },
        ],
    }
    return card


def supervisor_request_failed(user: str, initial_query: str) -> dict:
    """
    Creates a supervisor request failed card

    Args:
        user (str): user who submitted the query
        initial_query: query of the user

    Returns:
        card (dict)
    """
    card = {
        "cardsV2": [
            {
                "cardId": "aiResponseCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {"materialIcon": {"name": "feedback"}},
                                        "text": content.FAILURE,
                                        "bottomLabel": "Please provide support if the adviser doesn't retry",
                                    }
                                },
                                {
                                    "textParagraph": {
                                        "text": initial_query,
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "bottomLabel": user,
                                    }
                                },
                            ]
                        }
                    ],
                },
            },
        ],
    }
    return card


def supervisor_request_pending(user: str, initial_query: str) -> dict:
    """
    Creates a supervisor request pending card

    Args:
        user (str): user who submitted the query
        initial_query: query of the user

    Returns:
        card (dict)
    """
    card = {
        "cardsV2": [
            {
                "cardId": "aiResponseCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {"materialIcon": {"name": "pending"}},
                                        "text": '<b><font color="#004f88">AWAITING RESPONSE APPROVAL</font></b>',
                                    }
                                },
                                {
                                    "textParagraph": {
                                        "text": initial_query,
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "bottomLabel": user,
                                    }
                                },
                            ]
                        }
                    ],
                },
            },
        ],
    }
    return card


def rejection_json_widget(approver: str, supervisor_message: str) -> dict:
    """
    This takes in an approver and generates the rejection response widget

    Args:
        approver (str): the rejector of the message
        supervisor_message (str): rejection message from the supervisor
    Response:
        widget (dict)
    """
    widget = {
        "widgets": [
            {
                "decoratedText": {
                    "icon": {"materialIcon": {"name": "block"}},
                    "text": '<font color="#ec0101"><b>Response rejected</b></font>',
                    "bottomLabel": f"by {approver}",
                }
            },
        ]
    }

    if supervisor_message != "":
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        supervisor_message = re.sub(
            url_pattern, r'<a href="\g<0>">\g<0></a>', supervisor_message
        )
        widget["widgets"].append({"divider": {}})
        widget["widgets"].append(
            {
                "decoratedText": {
                    "topLabel": "Supervisor Notes",
                }
            }
        )
        widget["widgets"].append({"textParagraph": {"text": supervisor_message}})

    return widget


def call_complete_card(survey_card: dict) -> dict:
    """
    Creates a mark call complete button storing the survey card for when activated

    Args:
        survey_card: The post call sruvey

    Returns:
        Google Chat call complete button
    """
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

    return call_complete_card


def create_follow_up_questions_card(
    llm_output: LLMOutput,
    caddy_query: UserMessage,
    supervisor_message_id: Optional[str] = None,
    supervisor_thread_id: Optional[str] = None,
):
    """
    Create a follow-up questions card
    """
    sections = [
        {
            "header": "We need more information",
            "widgets": [
                {
                    "textParagraph": {
                        "text": "To provide a better answer, please respond to these follow-up questions:"
                    }
                },
            ],
        }
    ]

    for i, question in enumerate(llm_output.follow_up_questions, start=1):
        sections.append(
            {
                "widgets": [
                    {"textParagraph": {"text": question}},
                    {
                        "textInput": {
                            "label": f"Answer {i}",
                            "type": "MULTIPLE_LINE",
                            "name": f"follow_up_answer_{i}",
                        }
                    },
                ]
            }
        )

    sections.append(
        {
            "widgets": [
                {
                    "buttonList": {
                        "buttons": [
                            {
                                "text": "Submit",
                                "onClick": {
                                    "action": {
                                        "function": "handle_follow_up_answers",
                                        "parameters": [
                                            {
                                                "key": "original_query",
                                                "value": caddy_query.message,
                                            },
                                            {
                                                "key": "original_message",
                                                "value": llm_output.message,
                                            },
                                            {
                                                "key": "supervisor_message_id",
                                                "value": supervisor_message_id,
                                            },
                                            {
                                                "key": "supervisor_thread_id",
                                                "value": supervisor_thread_id,
                                            },
                                            {
                                                "key": "follow_up_questions",
                                                "value": json.dumps(
                                                    llm_output.follow_up_questions
                                                ),
                                            },
                                            {
                                                "key": "original_thread_id",
                                                "value": caddy_query.thread_id,
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
    )

    return {
        "cardsV2": [
            {
                "cardId": "follow_up_questions",
                "card": {
                    "sections": sections,
                },
            }
        ]
    }


def create_supervision_card(
    user_email: str,
    event: SupervisionEvent,
    new_request_message_id: str,
    request_approved: Dict[str, Any],
    request_rejected: Dict[str, Any],
    card_for_approval: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a supervision card
    """
    conversation_id = event.conversation_id
    response_id = event.response_id
    message_id = event.message_id
    thread_id = event.thread_id
    status_id = event.status_message_id

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
                                        {"key": "status_id", "value": status_id},
                                        {
                                            "key": "newRequestId",
                                            "value": new_request_message_id,
                                        },
                                        {"key": "userEmail", "value": user_email},
                                        {
                                            "key": "original_query",
                                            "value": event.llmPrompt,
                                        },
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
                                        {"key": "status_id", "value": status_id},
                                        {
                                            "key": "newRequestId",
                                            "value": new_request_message_id,
                                        },
                                        {"key": "userEmail", "value": user_email},
                                        {
                                            "key": "original_query",
                                            "value": event.llmPrompt,
                                        },
                                    ],
                                }
                            },
                        },
                    ]
                }
            },
        ],
    }

    card_for_approval_sections = list(
        card_for_approval["cardsV2"][0]["card"]["sections"]
    )
    card_for_approval_sections.append(approval_buttons_section)
    card_for_approval["cardsV2"][0]["card"]["sections"] = card_for_approval_sections

    return card_for_approval


def create_client_friendly_dialog(content: str) -> Dict[str, Any]:
    """
    Create dialog for client friendly content
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


def create_user_list_dialog(
    supervision_users: str, space_display_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create user list dialog
    """
    return {
        "action_response": {
            "type": "DIALOG",
            "dialog_action": {
                "dialog": {
                    "body": {
                        "sections": [
                            {
                                "header": (
                                    f"Supervision users for {space_display_name}"
                                    if space_display_name
                                    else "Supervision Users"
                                ),
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


def create_pii_warning_card(
    message: str, original_event: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create PII warning card with redaction options
    """
    return {
        "cardsV2": [
            {
                "cardId": "PIIDetected",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "icon": {"materialIcon": {"name": "warning"}},
                                        "text": '<font color="#FF0000"><b>PII Detected</b></font>',
                                        "bottomLabel": "Please ensure all queries are anonymised",
                                    }
                                },
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
                                                                    original_event
                                                                ),
                                                            }
                                                        ],
                                                    }
                                                },
                                            },
                                            {
                                                "text": "Edit message",
                                                "onClick": {
                                                    "action": {
                                                        "function": "edit_query_dialog",
                                                        "interaction": "OPEN_DIALOG",
                                                        "parameters": [
                                                            {
                                                                "key": "original_message",
                                                                "value": message,
                                                            }
                                                        ],
                                                    }
                                                },
                                            },
                                        ]
                                    }
                                },
                            ]
                        }
                    ]
                },
            }
        ]
    }


def edit_query_dialog(
    message_event: Dict[str, Any], message_string: str
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


def create_approved_card(
    self, card: Dict[str, Any], approver: str, supervisor_notes: str
) -> Dict[str, Any]:
    """
    Create an approved card with supervisor info
    """
    card["cardsV2"][0]["card"]["sections"].insert(
        0, self.responses.approval_json_widget(approver, supervisor_notes)
    )
    return card


def create_client_friendly_card(approved_card):
    """
    Update to card with button to invoke client friendly Caddy response
    """
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
                                }
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

    return approved_card


# --- Dialog Responses --- #

SUCCESS_DIALOG = JSONResponse(
    status_code=status.HTTP_200_OK,
    content=content.SUCCESS_DIALOG,
)

ADD_USER_DIALOG = JSONResponse(
    status_code=status.HTTP_200_OK, content=content.ADD_USER_DIALOG
)

REMOVE_USER_DIALOG = JSONResponse(
    status_code=status.HTTP_200_OK, content=content.REMOVE_USER_DIALOG
)

HELPER_DIALOG = JSONResponse(
    status_code=status.HTTP_200_OK, content=content.HELPER_DIALOG
)
