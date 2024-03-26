import os
from googleapiclient.discovery import build

from integrations.google_chat.content import MESSAGES
from integrations.google_chat.auth import get_google_creds

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
    def send_message_to_adviser_space(self, space_id: str, message, thread_id):
        response = (
            self.caddy.spaces()
            .messages()
            .create(
                parent=f"spaces/{space_id}",
                body={
                    "text": message,
                    "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
                },
                messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
            )
            .execute()
        )

        thread_id = response["thread"]["name"].split("/")[3]
        message_id = response["name"].split("/")[3]

        return thread_id, message_id

    # Update message in the adviser space
    @xray_recorder.capture()
    def update_message_in_adviser_space(self, space_id: str, message_id: str, message):
        self.caddy.spaces().messages().patch(
            name=f"spaces/{space_id}/messages/{message_id}",
            body=message,
            updateMask="text",
        ).execute()

    @xray_recorder.capture()
    def create_card(self, llm_response):
        card = {
            "cardsV2": [
                {
                    "cardId": "aiResponseCard",
                    "card": {
                        "sections": [],
                    },
                },
            ],
        }

        llm_response_section = {
            "widgets": [
                {"textParagraph": {"text": llm_response["result"]}},
            ],
        }

        card["cardsV2"][0]["card"]["sections"].append(llm_response_section)

        reference_links_section = {"header": "Reference links", "widgets": []}

        for document in llm_response["source_documents"]:
            reference_link = {
                "textParagraph": {
                    "text": f"<a href=\"{document.metadata['source_url']}\">{document.metadata['source_url']}</a>"
                }
            }
            if reference_link not in reference_links_section["widgets"]:
                reference_links_section["widgets"].append(reference_link)

        card["cardsV2"][0]["card"]["sections"].append(reference_links_section)

        return card
