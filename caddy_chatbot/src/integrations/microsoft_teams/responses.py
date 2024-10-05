from fastapi import status
from fastapi.responses import Response

# --- Status Responses --- #
NO_CONTENT = Response(status_code=status.HTTP_204_NO_CONTENT)
NOT_FOUND = Response(status_code=status.HTTP_404_NOT_FOUND)
ACCEPTED = Response(status_code=status.HTTP_202_ACCEPTED)
OK = Response(status_code=status.HTTP_200_OK)

# --- Microsoft Teams Cards --- #

PROCESSING_MESSAGE = [
    {
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "Image",
                        "url": "https://storage.googleapis.com/sort_assets/pending.png",
                        "size": "Small",
                        "height": "20px",
                    }
                ],
                "verticalContentAlignment": "Center",
            },
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Status",
                        "weight": "Bolder",
                        "size": "Small",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Requesting Caddy to help with this query",
                        "wrap": True,
                        "size": "Small",
                        "spacing": "None",
                    },
                ],
                "verticalContentAlignment": "Center",
            },
        ],
        "spacing": "Small",
    }
]

COMPOSING_MESSAGE = [
    {
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "Image",
                        "url": "https://storage.googleapis.com/sort_assets/notes.png",
                        "size": "Small",
                        "height": "20px",
                    }
                ],
                "verticalContentAlignment": "Center",
            },
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Status",
                        "weight": "Bolder",
                        "size": "Small",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Composing answer to your query",
                        "wrap": True,
                        "size": "Small",
                        "spacing": "None",
                    },
                ],
                "verticalContentAlignment": "Center",
            },
        ],
        "spacing": "Small",
    }
]

COMPOSING_RETRY = [
    {
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "Image",
                        "url": "https://storage.googleapis.com/sort_assets/refresh.png",
                        "size": "Small",
                        "height": "20px",
                    }
                ],
                "verticalContentAlignment": "Center",
            },
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Status",
                        "weight": "Bolder",
                        "size": "Small",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Composing answer to your query",
                        "wrap": True,
                        "size": "Small",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Something went wrong, retrying...",
                        "wrap": True,
                        "color": "Attention",
                        "size": "Small",
                        "spacing": "None",
                    },
                ],
                "verticalContentAlignment": "Center",
            },
        ],
        "spacing": "Small",
    }
]

REQUEST_FAILED = [
    {
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "Image",
                        "url": "https://storage.googleapis.com/sort_assets/feedback.png",
                        "size": "Small",
                        "height": "20px",
                    }
                ],
                "verticalContentAlignment": "Center",
            },
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Status",
                        "weight": "Bolder",
                        "size": "Small",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Caddy failed to respond",
                        "wrap": True,
                        "color": "Attention",
                        "size": "Small",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Please try again shortly",
                        "wrap": True,
                        "size": "Small",
                        "spacing": "None",
                    },
                ],
                "verticalContentAlignment": "Center",
            },
        ],
        "spacing": "Small",
    }
]

SUPERVISOR_REVIEWING = [
    {
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "Image",
                        "url": "https://storage.googleapis.com/sort_assets/quick_reference_all.png",
                        "size": "Small",
                        "height": "20px",
                    }
                ],
                "verticalContentAlignment": "Center",
            },
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Status",
                        "weight": "Bolder",
                        "size": "Small",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Supervisor reviewing response",
                        "wrap": True,
                        "size": "Small",
                        "spacing": "None",
                    },
                ],
                "verticalContentAlignment": "Center",
            },
        ],
        "spacing": "Small",
    }
]

AWAITING_APPROVAL = [
    {
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "Image",
                        "url": "https://storage.googleapis.com/sort_assets/supervisor_account.png",
                        "size": "Small",
                        "height": "20px",
                    }
                ],
                "verticalContentAlignment": "Center",
            },
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Status",
                        "weight": "Bolder",
                        "size": "Small",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Awaiting approval",
                        "wrap": True,
                        "size": "Small",
                        "spacing": "None",
                    },
                ],
                "verticalContentAlignment": "Center",
            },
        ],
        "spacing": "Small",
    }
]

UNAUTHORISED_SUPERVISOR_ACCESS = [
    {
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "Image",
                        "url": "https://storage.googleapis.com/sort_assets/supervised_user_circle_off.png",
                        "size": "Small",
                        "height": "20px",
                    }
                ],
                "verticalContentAlignment": "Center",
            },
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Unauthorised",
                        "weight": "Bolder",
                        "size": "Small",
                        "color": "Attention",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Only registered supervisors are able to access this functionality",
                        "wrap": True,
                        "size": "Small",
                        "spacing": "None",
                    },
                ],
                "verticalContentAlignment": "Center",
            },
        ],
        "spacing": "Small",
    }
]

HELPER_GUIDE = {
    "type": "AdaptiveCard",
    "body": [
        {
            "type": "TextBlock",
            "text": "Caddy Supervision Commands",
            "weight": "Bolder",
            "size": "Medium",
        },
        {
            "type": "TextBlock",
            "text": "• addUser: Add a new user to Caddy\n• removeUser: Remove a user from Caddy\n• listUsers: List all users in the supervision space\n• help: Display this help information",
            "wrap": True,
        },
    ],
    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    "version": "1.2",
}


def create_error_card(error_message: str):
    return {
        "type": "AdaptiveCard",
        "body": [
            {
                "type": "TextBlock",
                "text": error_message,
                "wrap": True,
                "color": "Attention",
            }
        ],
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.2",
    }


def create_user_list_card(user_list: str):
    return {
        "type": "AdaptiveCard",
        "body": [
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "Image",
                                "url": "https://storage.googleapis.com/sort_assets/groups.png",
                                "size": "Small",
                                "height": "20px",
                            }
                        ],
                        "verticalContentAlignment": "Center",
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "Registered Users",
                                "weight": "Bolder",
                                "size": "Medium",
                                "spacing": "None",
                            },
                        ],
                        "verticalContentAlignment": "Center",
                    },
                ],
                "spacing": "Small",
            },
            {"type": "TextBlock", "text": user_list, "wrap": True},
        ],
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.2",
    }


def create_remove_user_card(choices, status_message, status_colour):
    return {
        "type": "AdaptiveCard",
        "body": [
            {
                "type": "TextBlock",
                "text": "Remove a user from Caddy",
                "weight": "Bolder",
                "size": "Medium",
            },
            (
                {
                    "type": "Input.ChoiceSet",
                    "id": "teamsUser",
                    "label": "Select user to remove",
                    "choices": choices,
                }
                if choices
                else {
                    "type": "TextBlock",
                    "text": "No enrolled users found.",
                    "color": "Attention",
                }
            ),
            {
                "type": "TextBlock",
                "text": status_message,
                "wrap": True,
                "color": status_colour,
            },
        ],
        "actions": (
            [
                {
                    "type": "Action.Submit",
                    "title": "Remove User",
                    "data": {"action": "removeUser"},
                }
            ]
            if choices
            else []
        ),
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.2",
    }


def create_remove_user_dialog(choices):
    return {
        "type": "AdaptiveCard",
        "body": [
            {
                "type": "TextBlock",
                "text": "Remove a user from Caddy",
                "weight": "Bolder",
                "size": "Medium",
            },
            (
                {
                    "type": "Input.ChoiceSet",
                    "id": "teamsUser",
                    "label": "Select user to remove",
                    "choices": choices,
                }
                if choices
                else {
                    "type": "TextBlock",
                    "text": "No enrolled users found.",
                    "color": "Attention",
                }
            ),
        ],
        "actions": (
            [
                {
                    "type": "Action.Submit",
                    "title": "Remove User",
                    "data": {"action": "removeUser"},
                }
            ]
            if choices
            else []
        ),
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.2",
    }


def create_add_user_card(choices, status_message, status_colour):
    return {
        "type": "AdaptiveCard",
        "body": [
            {
                "type": "TextBlock",
                "text": "Add a new user to Caddy",
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": "Input.ChoiceSet",
                "id": "teamsUser",
                "label": "Select user",
                "choices": choices,
            },
            {
                "type": "Input.ChoiceSet",
                "id": "role",
                "label": "User's role",
                "choices": [
                    {"title": "Adviser", "value": "Adviser"},
                    {"title": "Supervisor", "value": "Supervisor"},
                ],
            },
            {
                "type": "TextBlock",
                "text": status_message,
                "wrap": True,
                "color": status_colour,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Add User",
                "data": {"action": "addUser"},
            }
        ],
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.2",
    }


def create_add_user_dialog(users):
    return {
        "type": "AdaptiveCard",
        "body": [
            {
                "type": "TextBlock",
                "text": "Add a new user to Caddy",
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": "Input.ChoiceSet",
                "id": "teamsUser",
                "label": "Select user",
                "choices": users,
            },
            {
                "type": "Input.ChoiceSet",
                "id": "role",
                "label": "User's role",
                "choices": [
                    {"title": "Adviser", "value": "Adviser"},
                    {"title": "Supervisor", "value": "Supervisor"},
                ],
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Add User",
                "data": {"action": "addUser"},
            }
        ],
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.2",
    }
