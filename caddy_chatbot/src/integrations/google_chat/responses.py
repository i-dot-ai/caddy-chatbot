from fastapi import status
from fastapi.responses import JSONResponse, Response
from integrations.google_chat import content
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
                                        "topLabel": "Supervisor override",
                                        "text": '<font color="#ec0101"><B>Caddy response rejected<b></font>',
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

    card["cardsV2"][0]["card"]["sections"][0]["widgets"].append(
        {
            "decoratedText": {
                "bottomLabel": f"{approver}",
            }
        }
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
                "cardId": "aiResponseCard",
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
