from fastapi import status
from fastapi.responses import Response

# --- Status Responses --- #
NO_CONTENT = Response(status_code=status.HTTP_204_NO_CONTENT)
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
