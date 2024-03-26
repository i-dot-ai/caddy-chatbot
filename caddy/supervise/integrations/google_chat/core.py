import os
from googleapiclient.discovery import build
from integrations.google_chat.auth import get_google_creds
from integrations.google_chat.content import MESSAGES

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
    def send_message_to_supervisor_space(self, space_id, message):
        response = (
            self.supervisor.spaces()
            .messages()
            .create(parent=f"spaces/{space_id}", body=message)
            .execute()
        )

        thread_id = response["thread"]["name"].split("/")[3]
        message_id = response["name"].split("/")[3]

        return thread_id, message_id

    @xray_recorder.capture()
    def respond_to_supervisor_thread(self, space_id, message, thread_id):
        self.supervisor.spaces().messages().create(
            parent=f"spaces/{space_id}",
            body={
                "cardsV2": message["cardsV2"],
                "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
            },
            messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
        ).execute()
