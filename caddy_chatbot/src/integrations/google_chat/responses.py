from fastapi import status
from fastapi.responses import JSONResponse, Response
from integrations.google_chat import content
import re

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
    url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    supervisor_message = re.sub(
        url_pattern, r'<a href="\g<0>">\g<0></a>', supervisor_message
    )

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
                                {"divider": {}},
                                {
                                    "decoratedText": {
                                        "topLabel": "Supervisor response",
                                    }
                                },
                                {"textParagraph": {"text": supervisor_message}},
                                {
                                    "decoratedText": {
                                        "bottomLabel": f"{approver}",
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


def control_group_selection(control_group_message) -> dict:
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
                            ]
                        }
                    ]
                },
            },
        ],
    }
    return card


def approval_json_widget(approver: str) -> dict:
    """
    This takes in an approver and generates the approved response widget

    Args:
        approver (str): the approver of the message

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
                }
            }
        ]
    }
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
                                    "decoratedText": {
                                        "text": initial_query,
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
                                    "decoratedText": {
                                        "text": initial_query,
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
                                    "decoratedText": {
                                        "text": initial_query,
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
            {
                "textParagraph": {
                    "text": f'<font color="#004f88"><b>Supervisor response</b> \n\n {supervisor_message}</font>'
                }
            },
        ]
    }

    return widget


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
