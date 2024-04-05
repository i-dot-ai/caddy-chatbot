import os
from googleapiclient.discovery import build

from integrations.google_chat.content import MESSAGES
from integrations.google_chat.auth import get_google_creds
from caddy.services.survey import get_survey

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
    def create_card(self, llm_response, source_documents):
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
                {"textParagraph": {"text": llm_response.llm_answer}},
            ],
        }

        card["cardsV2"][0]["card"]["sections"].append(llm_response_section)

        reference_links_section = {"header": "Reference links", "widgets": []}

        for document in source_documents:
            reference_link = {
                "textParagraph": {
                    "text": f"<a href=\"{document.metadata['source_url']}\">{document.metadata['source_url']}</a>"
                }
            }
            if reference_link not in reference_links_section["widgets"]:
                reference_links_section["widgets"].append(reference_link)

        card["cardsV2"][0]["card"]["sections"].append(reference_links_section)

        return card
    
    @xray_recorder.capture()
    def send_dynamic_to_adviser_space(
        self, response_type, space_id, message, thread_id
    ):
        match response_type:
            case "text":
                self.caddy.spaces().messages().create(
                    parent=f"spaces/{space_id}",
                    body={
                        "text": message,
                        "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
                    },
                    messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
                ).execute()
            case "cardsV2":
                self.caddy.spaces().messages().create(
                    parent=f"spaces/{space_id}",
                    body={
                        "cardsV2": message["cardsV2"],
                        "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
                    },
                    messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
                ).execute()
    
    @xray_recorder.capture()
    def get_post_call_survey_card(
        self, post_call_survey_questions, post_call_survey_values
    ):
        card = {
            "cardsV2": [
                {
                    "cardId": "postCallSurvey",
                    "card": {
                        "sections": [],
                    },
                },
            ],
        }

        for question in post_call_survey_questions:
            section = {"widgets": []}

            question_section = {"textParagraph": {"text": question}}

            button_section = {"buttonList": {"buttons": []}}

            for value in post_call_survey_values:
                button_section["buttonList"]["buttons"].append(
                    {
                        "text": value,
                        "onClick": {
                            "action": {
                                "function": "survey_response",
                                "parameters": [
                                    {"key": "question", "value": question},
                                    {"key": "response", "value": value},
                                ],
                            }
                        },
                    }
                )

            section["widgets"].append(question_section)
            section["widgets"].append(button_section)

            card["cardsV2"][0]["card"]["sections"].append(section)

        return card

    @xray_recorder.capture()
    def run_survey(self, user: str, thread_id: str, user_space: str) -> None:
        """
        Run a survey in the adviser space by getting the survey questions and values by providing a user to the get_survey function

        Args:
            survey_card (dict): The survey card to run
            user_space (str): The space ID of the user
            thread_id (str): The thread ID of the conversation

        Returns:
            None
        """
        post_call_survey_questions, post_call_survey_values = get_survey(user)

        survey_card = self.get_post_call_survey_card(
            post_call_survey_questions, post_call_survey_values
        )

        self.send_dynamic_to_adviser_space(
            response_type="cardsV2",
            space_id=user_space,
            message=survey_card,
            thread_id=thread_id,
        )