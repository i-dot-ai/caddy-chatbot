from typing import List, Dict
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


def generate_response_card(llm_response):
    """
    Creates a Teams Adaptive card given a Caddy response
    """
    caddy_response = [
        {"type": "TextBlock", "text": llm_response, "wrap": True},
        {"type": "ActionSet", "id": "referenceLinks", "actions": []},
        {
            "type": "ActionSet",
            "id": "approvalButtons",
            "actions": [
                {
                    "type": "Action.Execute",
                    "title": "👍",
                    "verb": "approved",
                    "data": {"action": "approved"},
                },
                {
                    "type": "Action.Execute",
                    "title": "👎",
                    "verb": "rejected",
                    "data": {"action": "rejected"},
                },
            ],
        },
    ]

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
            "title": f"{ref} - {url}",
            "url": url,
        }
        caddy_response[1]["actions"].append(reference_link)

        processed_urls.append(url)

    llm_response = llm_response.replace("<b>", "**").replace("</b>", "**")
    llm_response = llm_response.replace('<font color="#004f88">', "_").replace(
        "</font>", "_"
    )
    caddy_response[0]["text"] = llm_response

    return caddy_response


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


def create_approval_confirmation_card(caddy_message) -> List[Dict]:
    """
    Creates a Teams Adaptive card to confirm approval in the supervision space
    """
    confirmation_card = [
        {
            "type": "TextBlock",
            "text": "Message approved",
            "weight": "bolder",
            "size": "medium",
            "color": "good",
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "From:", "value": caddy_message.name},
                {"title": "Message:", "value": caddy_message.message_string},
            ],
        },
    ]
    return confirmation_card


def create_rejection_card() -> List[Dict]:
    rejection_card = [
        {
            "type": "TextBlock",
            "text": "Supervisor rejected Caddy response.",
            "weight": "bolder",
            "size": "medium",
            "color": "attention",
        },
    ]
    return rejection_card


def create_rejection_confirmation_card(caddy_message) -> List[Dict]:
    confirmation_card = [
        {
            "type": "TextBlock",
            "text": "Message rejected",
            "weight": "bolder",
            "size": "medium",
            "color": "attention",
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "From:", "value": caddy_message.name},
                {"title": "Message:", "value": caddy_message.message_string},
            ],
        },
    ]
    return confirmation_card


def create_supervision_card(caddy_message, llm_response, context_sources) -> List[Dict]:
    supervision_card = [
        {
            "type": "TextBlock",
            "text": "New message for approval",
            "weight": "bolder",
            "size": "medium",
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "From:", "value": caddy_message.name},
                {"title": "Message:", "value": caddy_message.message_string},
            ],
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
            "items": [
                {
                    "type": "TextBlock",
                    "text": llm_response,
                    "wrap": True,
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {
                            "title": "Context Sources:",
                            "value": ", ".join(context_sources),
                        }
                    ],
                },
            ],
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
                    },
                },
                {
                    "type": "Action.Execute",
                    "title": "Reject",
                    "verb": "rejected",
                    "data": {
                        "action": "rejected",
                        "original_message": caddy_message.__dict__,
                    },
                },
            ],
        },
    ]
    return supervision_card
