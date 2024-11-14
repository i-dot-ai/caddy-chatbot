from typing import List, Dict, Optional
from caddy_core.models import LLMOutput, UserMessage
import re

CADDY_PROCESSING = [
    {
        "type": "Container",
        "items": [
            {
                "type": "TextBlock",
                "text": "🦉 Processing request...",
                "weight": "bolder",
                "size": "medium",
            },
        ],
    },
]


def create_pii_detected_card(query: str) -> List[Dict]:
    """
    Takes a message query and returns a PII Detected field with optional redaction input
    """
    PII_DETECTED = [
        {
            "type": "RichTextBlock",
            "inlines": [
                {
                    "type": "TextRun",
                    "text": "PII Detected",
                    "color": "attention",
                    "weight": "bolder",
                },
                {
                    "type": "TextRun",
                    "text": " Please ensure all queries to Caddy are anonymised.",
                    "italic": True,
                },
            ],
        },
        {
            "type": "RichTextBlock",
            "id": "buttonText",
            "inlines": [
                {
                    "type": "TextRun",
                    "text": "Choose whether to proceed anyway or edit your original query",
                }
            ],
        },
        {
            "type": "ActionSet",
            "id": "redactionButtons",
            "actions": [
                {
                    "type": "Action.Execute",
                    "title": "Proceed without redaction",
                    "verb": "proceed",
                    "data": {"action": "proceed"},
                },
                {
                    "type": "Action.ToggleVisibility",
                    "title": "Edit original query",
                    "targetElements": [
                        {"elementId": "queryText", "isVisible": True},
                        {"elementId": "redactedQuerySubmission", "isVisible": True},
                        {"elementId": "redactionButtons", "isVisible": False},
                        {"elementId": "buttonText", "isVisible": False},
                    ],
                },
            ],
        },
        {"type": "Input.Text", "id": "queryText", "isVisible": False, "value": query},
        {
            "type": "ActionSet",
            "id": "redactedQuerySubmission",
            "isVisible": False,
            "actions": [
                {
                    "type": "Action.Execute",
                    "title": "Submit Redaction",
                    "verb": "redacted_query",
                    "data": {"action": "redacted_query"},
                },
            ],
        },
    ]
    return PII_DETECTED


def create_redacted_card(event) -> List[Dict]:
    """
    Takes in a redaction event and created a redacted query card
    """
    redacted_query = event["value"]["action"]["data"]["queryText"]
    REDACTED = [
        {
            "type": "RichTextBlock",
            "inlines": [
                {
                    "type": "TextRun",
                    "text": "Query redacted: ",
                    "color": "good",
                    "weight": "bolder",
                },
                {"type": "TextRun", "text": redacted_query, "italic": True},
            ],
        }
    ]
    return REDACTED


def generate_response_card(
    llm_response: str, context_sources: Optional[List[str]] = []
) -> List[Dict]:
    """
    Creates a Teams Adaptive Card for the Caddy response
    """
    card_body = [
        {"type": "TextBlock", "text": llm_response, "wrap": True},
    ]

    reference_links = []

    pattern = r"<ref>(?:SOURCE_URL:)?(http[s]?://[^>]+)</ref>"
    urls = re.findall(pattern, llm_response)
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
            f"<ref>{url}</ref>", f"[{ref} - {resource}]({url})"
        )
        llm_response = llm_response.replace(
            f"<ref>SOURCE_URL:{url}</ref>", f"[{ref} - {resource}]({url})"
        )

        reference_link = {
            "type": "Action.OpenUrl",
            "title": f"{ref} - {resource}",
            "url": url,
        }
        reference_links.append(reference_link)

        processed_urls.append(url)

    llm_response = llm_response.replace("<b>", "**").replace("</b>", "**")
    llm_response = llm_response.replace('<font color="#004f88">', "_").replace(
        "</font>", "_"
    )
    card_body[0]["text"] = llm_response

    if reference_links:
        card_body.append(
            {
                "type": "TextBlock",
                "text": "Reference links",
                "weight": "Bolder",
                "size": "Medium",
                "spacing": "Medium",
            }
        )
        card_body.append({"type": "ActionSet", "actions": reference_links})

    return card_body


def create_approved_response_card(caddy_message) -> List[Dict]:
    """
    Creates a Teams Adaptive card for the approved response
    """
    approved_card = [
        {
            "type": "TextBlock",
            "text": "Your message has been approved",
            "weight": "bolder",
            "size": "medium",
        },
        {
            "type": "TextBlock",
            "text": caddy_message.message_string,
            "wrap": True,
        },
    ]
    return approved_card


def create_approval_confirmation_card(
    caddy_message, supervisor_notes, supervisor_name, llm_response
) -> Dict:
    """
    Creates a Teams Adaptive card to confirm approval in the supervision space
    """
    confirmation_card_body = [
        {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "auto",
                    "items": [
                        {
                            "type": "Image",
                            "url": "https://storage.googleapis.com/sort_assets/verified.png",
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
                            "text": "RESPONSE APPROVED",
                            "weight": "Bolder",
                            "size": "Small",
                            "color": "Good",
                            "spacing": "None",
                        },
                        {
                            "type": "TextBlock",
                            "text": f"by {supervisor_name}",
                            "wrap": True,
                            "size": "Small",
                            "spacing": "None",
                            "isSubtle": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": caddy_message.message_string,
                            "wrap": True,
                            "size": "Small",
                            "spacing": "Small",
                        },
                        {
                            "type": "TextBlock",
                            "text": f"{caddy_message.name}",
                            "wrap": True,
                            "size": "Small",
                            "spacing": "Small",
                            "isSubtle": True,
                        },
                    ],
                    "verticalContentAlignment": "Center",
                },
            ],
        }
    ]

    if supervisor_notes:
        url_pattern = r"(https?://\S+)"
        supervisor_notes_with_links = re.sub(url_pattern, r"[\1](\1)", supervisor_notes)

        confirmation_card_body.append(
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "Supervisor Notes",
                                "weight": "Bolder",
                                "size": "Small",
                                "spacing": "Medium",
                            },
                            {
                                "type": "TextBlock",
                                "text": supervisor_notes_with_links,
                                "wrap": True,
                                "size": "Small",
                                "spacing": "Small",
                            },
                        ],
                    },
                ],
            }
        )

    confirmation_card_body.append(
        {
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.ToggleVisibility",
                    "title": "Toggle Caddy Response",
                    "targetElements": ["llmResponseContainer"],
                },
            ],
        }
    )

    confirmation_card_body.append(
        {
            "type": "Container",
            "id": "llmResponseContainer",
            "isVisible": False,
            "items": generate_response_card(llm_response, []),
        }
    )

    return {
        "type": "AdaptiveCard",
        "body": confirmation_card_body,
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.2",
    }


def create_rejection_card(supervisor_notes, supervisor_name) -> List[Dict]:
    url_pattern = r"(https?://\S+)"
    supervisor_notes_with_links = re.sub(url_pattern, r"[\1](\1)", supervisor_notes)

    rejection_card = [
        {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "auto",
                    "items": [
                        {
                            "type": "Image",
                            "url": "https://storage.googleapis.com/sort_assets/block.png",
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
                            "text": "RESPONSE REJECTED",
                            "weight": "Bolder",
                            "size": "Small",
                            "color": "Attention",
                            "spacing": "None",
                        },
                        {
                            "type": "TextBlock",
                            "text": "Supervisor override",
                            "weight": "Bolder",
                            "size": "Small",
                            "spacing": "None",
                        },
                    ],
                    "verticalContentAlignment": "Center",
                },
            ],
            "spacing": "Small",
        },
        {
            "type": "TextBlock",
            "text": "Supervisor Notes",
            "weight": "Bolder",
            "size": "Small",
            "spacing": "Medium",
        },
        {
            "type": "TextBlock",
            "text": supervisor_notes_with_links,
            "wrap": True,
            "size": "Small",
            "spacing": "Small",
        },
        {
            "type": "TextBlock",
            "text": f"{supervisor_name}",
            "wrap": True,
            "size": "Small",
            "spacing": "Small",
            "isSubtle": True,
        },
    ]

    return rejection_card


def create_rejection_confirmation_card(
    caddy_message, supervisor_notes, supervisor_name, llm_response
) -> Dict:
    confirmation_card = [
        {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "auto",
                    "items": [
                        {
                            "type": "Image",
                            "url": "https://storage.googleapis.com/sort_assets/block.png",
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
                            "text": "RESPONSE REJECTED",
                            "weight": "Bolder",
                            "size": "Small",
                            "color": "Attention",
                            "spacing": "None",
                        },
                        {
                            "type": "TextBlock",
                            "text": f"by {supervisor_name}",
                            "wrap": True,
                            "size": "Small",
                            "spacing": "None",
                            "isSubtle": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": caddy_message.message_string,
                            "wrap": True,
                            "size": "Small",
                            "spacing": "Small",
                        },
                        {
                            "type": "TextBlock",
                            "text": f"{caddy_message.name}",
                            "wrap": True,
                            "size": "Small",
                            "spacing": "Small",
                            "isSubtle": True,
                        },
                    ],
                    "verticalContentAlignment": "Center",
                },
            ],
            "spacing": "Small",
        }
    ]

    if supervisor_notes:
        url_pattern = r"(https?://\S+)"
        supervisor_notes_with_links = re.sub(url_pattern, r"[\1](\1)", supervisor_notes)

        confirmation_card.append(
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "Supervisor Notes",
                                "weight": "Bolder",
                                "size": "Small",
                                "spacing": "Medium",
                            },
                            {
                                "type": "TextBlock",
                                "text": supervisor_notes_with_links,
                                "wrap": True,
                                "size": "Small",
                                "spacing": "Small",
                            },
                        ],
                    },
                ],
            }
        )

    confirmation_card.append(
        {
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.ToggleVisibility",
                    "title": "Toggle Caddy Response",
                    "targetElements": ["llmResponseContainer"],
                },
            ],
        }
    )

    confirmation_card.append(
        {
            "type": "Container",
            "id": "llmResponseContainer",
            "isVisible": False,
            "items": generate_response_card(llm_response, []),
        }
    )

    return {
        "type": "AdaptiveCard",
        "body": confirmation_card,
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.2",
    }


def create_supervision_card(
    caddy_message, llm_response, context_sources, status_activity_id
) -> List[Dict]:
    """
    Creates a supervision card for the adviser request
    """
    supervision_card = [
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
                            "text": "AWAITING RESPONSE APPROVAL",
                            "weight": "Bolder",
                            "size": "Small",
                            "color": "Accent",
                            "spacing": "None",
                        },
                        {
                            "type": "TextBlock",
                            "text": caddy_message.message,
                            "wrap": True,
                            "size": "Small",
                            "spacing": "Small",
                        },
                        {
                            "type": "TextBlock",
                            "text": caddy_message.teams_from["name"],
                            "wrap": True,
                            "size": "Small",
                            "spacing": "None",
                            "isSubtle": True,
                        },
                    ],
                    "verticalContentAlignment": "Center",
                },
            ],
            "spacing": "Small",
        },
        {
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.ToggleVisibility",
                    "title": "Toggle Caddy Response",
                    "targetElements": ["llmResponseContainer"],
                },
            ],
        },
        {
            "type": "Container",
            "id": "llmResponseContainer",
            "isVisible": False,
            "items": generate_response_card(llm_response, []),
        },
        {
            "type": "Input.Text",
            "id": "supervisorNotes",
            "placeholder": "Add approval notes or an override response for rejection",
            "isMultiline": True,
        },
        {
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.Execute",
                    "title": "Approve",
                    "verb": "approved",
                    "data": {
                        "action": "approved",
                        "original_message": caddy_message.__dict__,
                        "llm_response": llm_response,
                        "context_sources": context_sources,
                        "status_activity_id": status_activity_id,
                    },
                },
                {
                    "type": "Action.Execute",
                    "title": "Reject",
                    "verb": "rejected",
                    "data": {
                        "action": "rejected",
                        "original_message": caddy_message.__dict__,
                        "llm_response": llm_response,
                        "context_sources": context_sources,
                        "status_activity_id": status_activity_id,
                    },
                },
            ],
        },
    ]
    return supervision_card


def update_response_card_with_supervisor_info(
    card_body, supervisor_notes, supervisor_name
):
    approval_section = {
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "Image",
                        "url": "https://storage.googleapis.com/sort_assets/verified.png",
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
                        "text": "RESPONSE APPROVED",
                        "weight": "Bolder",
                        "size": "Small",
                        "color": "Good",
                        "spacing": "None",
                    },
                    {
                        "type": "TextBlock",
                        "text": f"by {supervisor_name}",
                        "size": "Small",
                        "spacing": "None",
                        "isSubtle": True,
                    },
                ],
                "verticalContentAlignment": "Center",
            },
        ],
    }

    card_body.insert(0, approval_section)

    if supervisor_notes:
        url_pattern = r"(https?://\S+)"
        supervisor_notes_with_links = re.sub(url_pattern, r"[\1](\1)", supervisor_notes)

        supervisor_notes_section = {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "Supervisor Notes",
                            "weight": "Bolder",
                            "size": "Small",
                            "spacing": "Medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": supervisor_notes_with_links,
                            "wrap": True,
                            "size": "Small",
                            "spacing": "Small",
                        },
                    ],
                },
            ],
        }
        card_body.insert(1, supervisor_notes_section)

    card_body = [
        section
        for section in card_body
        if section.get("type") != "ActionSet"
        or "approvalButtons" not in section.get("id", "")
    ]

    return card_body


def create_teams_follow_up_questions_card(
    llm_output: LLMOutput,
    caddy_query: UserMessage,
    supervisor_message_id: Optional[str] = None,
    supervisor_thread_id: Optional[str] = None,
) -> Dict:
    """
    Create a follow up questions card for Microsoft Teams
    """
    card_body = [
        {
            "type": "TextBlock",
            "text": "We need more information",
            "weight": "Bolder",
            "size": "Medium",
        },
        {
            "type": "TextBlock",
            "text": "To provide a better answer, please respond to these follow-up questions:",
            "wrap": True,
        },
    ]

    for i, question in enumerate(llm_output.follow_up_questions, start=1):
        card_body.extend(
            [
                {
                    "type": "TextBlock",
                    "text": question,
                    "wrap": True,
                    "spacing": "Medium",
                },
                {
                    "type": "Input.Text",
                    "id": f"follow_up_answer_{i}",
                    "placeholder": f"Answer {i}",
                    "isMultiline": True,
                    "spacing": "Small",
                },
            ]
        )

    card_body.append(
        {
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.Execute",
                    "title": "Submit",
                    "verb": "follow_up_submission",
                    "data": {
                        "action": "follow_up_submission",
                        "original_query": caddy_query.message,
                        "original_message": llm_output.message,
                        "follow_up_questions": llm_output.follow_up_questions,
                        "original_thread_id": caddy_query.thread_id,
                        "teams_recipient": caddy_query.teams_recipient,
                        "teams_conversation": caddy_query.teams_conversation,
                        "teams_from": caddy_query.teams_from,
                    },
                }
            ],
        }
    )

    return card_body
