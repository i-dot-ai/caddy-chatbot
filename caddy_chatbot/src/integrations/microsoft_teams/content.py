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
