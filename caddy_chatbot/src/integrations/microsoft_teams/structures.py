import os
import json
import requests
from caddy_core.models import CaddyMessageEvent, ApprovalEvent
from caddy_core.utils.monitoring import logger
from caddy_core.services.anonymise import analyse
from integrations.microsoft_teams import content, responses
from datetime import datetime

from caddy_core import components as caddy

from .verification import get_access_token


class MicrosoftTeams:
    def __init__(self, supervision_space_id=None):
        self.client = "Microsoft Teams"
        self.access_token = get_access_token()
        self.messages = content
        self.responses = responses
        self.bot_id = os.getenv("TEAMS_BOT_ID")
        self.bot_name = "Caddy"
        self.supervision_space_id = supervision_space_id

    def send_adviser_card(self, event: CaddyMessageEvent, card=None):
        """
        Takes an incoming request from Teams Chat and returns a given response card
        """
        if card is None:
            card = self.messages.CADDY_PROCESSING

        conversation_id = event.teams_conversation["id"]
        activity_id = event.message_id
        service_url = event.teams_service_url

        response_url = (
            f"{service_url}/v3/conversations/{conversation_id}/activities/{activity_id}"
        )

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        response_activity = {
            "type": "message",
            "from": event.teams_recipient,
            "conversation": event.teams_conversation,
            "recipient": event.teams_from,
            "replyToId": activity_id,
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.0",
                        "body": card,
                    },
                }
            ],
        }

        response = requests.post(
            response_url, json=response_activity, headers=headers, timeout=60
        )

        logger.debug(response.json())
        return response.json().get("id")

    def update_card(self, event, card=None):
        """
        Updates an existing teams message given a card and action event
        """
        if card is None:
            card = self.messages.CADDY_PROCESSING

        conversation_id = event["conversation"]["id"]
        activity_id = event["id"]
        service_url = event["serviceUrl"]
        reply_to_id = event["replyToId"]

        response_url = (
            f"{service_url}/v3/conversations/{conversation_id}/activities/{reply_to_id}"
        )

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        response_activity = {
            "type": "message",
            "from": event["recipient"],
            "conversation": event["conversation"],
            "recipient": event["from"],
            "replyToId": activity_id,
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.0",
                        "body": card,
                    },
                }
            ],
        }

        response = requests.put(
            response_url, json=response_activity, headers=headers, timeout=60
        )

        logger.debug(response.json())

    def format_message(self, event):
        """
        Receives a message from Microsoft Teams and formats it into a Caddy message event
        """
        message_string = event["text"].replace("@Caddy", "")

        if "proceed" not in event:
            pii_identified = analyse(message_string)

            if pii_identified:
                # Optionally redact PII from the message by importing redact from services.anonymise
                # message_string = redact(message_string, pii_identified)

                self.send_adviser_card(
                    event=event,
                    card=self.messages.create_pii_detected_card(message_string),
                )
                return "PII Detected"

            caddy_message = CaddyMessageEvent(
                type="PROCESS_CHAT_MESSAGE",
                user=event["from"]["id"],
                name=event["from"]["name"],
                space_id=event["channelId"],
                message_id=event["id"],
                message_string=message_string,
                thread_id=event["id"],
                source_client=self.client,
                timestamp=str(event["timestamp"]),
                teams_conversation=event["conversation"],
                teams_from=event["from"],
                teams_recipient=event["recipient"],
                teams_service_url=event["serviceUrl"],
            )

        return caddy_message

    def json_serialise(self, obj):
        if isinstance(obj, dict):
            return {k: self.json_serialise(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.json_serialise(i) for i in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, CaddyMessageEvent):
            return self.json_serialise(obj.__dict__)
        else:
            return obj

    def send_to_supervision(
        self, caddy_message, llm_response, context_sources, status_activity_id
    ):
        supervision_card = self.messages.create_supervision_card(
            caddy_message, llm_response, context_sources, status_activity_id
        )

        service_url = caddy_message.teams_service_url
        response_url = (
            f"{service_url}/v3/conversations/{self.supervision_space_id}/activities"
        )

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        response_activity = {
            "type": "message",
            "from": {"id": self.bot_id, "name": self.bot_name},
            "conversation": {"id": self.supervision_space_id},
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": supervision_card,
                    },
                }
            ],
        }

        response_activity = self.json_serialise(response_activity)

        try:
            response = requests.post(
                response_url, json=response_activity, headers=headers, timeout=60
            )
            response.raise_for_status()
            logger.debug(f"Supervision message sent: {response.json()}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending supervision message: {str(e)}")
            logger.debug(f"Response content: {response.text}")

    def handle_approval(self, event):
        logger.info(f"Received approval event: {json.dumps(event, indent=2)}")

        try:
            if "value" in event and isinstance(event["value"], dict):
                action_data = event["value"].get("action", {}).get("data", {})
            elif "data" in event:
                action_data = event["data"]
            else:
                action_data = event

            original_message = action_data.get("original_message", {})
            llm_response = action_data.get("llm_response", "")
            context_sources = action_data.get("context_sources", [])
            status_activity_id = action_data.get("status_activity_id", "")
            supervisor_notes = action_data.get("supervisorNotes", "")
            supervisor_name = event["from"]["name"]

            logger.debug(
                f"Extracted data: original_message={original_message}, llm_response={llm_response}, context_sources={context_sources}, supervisor_notes={supervisor_notes}"
            )

            caddy_message = CaddyMessageEvent(
                type="APPROVED_MESSAGE",
                user=original_message.get("user"),
                name=original_message.get("name"),
                space_id=original_message.get("space_id"),
                message_id=original_message.get("message_id"),
                message_string=original_message.get("message_string"),
                source_client=self.client,
                timestamp=original_message.get("timestamp"),
                teams_conversation=original_message.get("teams_conversation"),
                teams_from=original_message.get("teams_from"),
                teams_recipient=original_message.get("teams_recipient"),
                teams_service_url=original_message.get("teams_service_url"),
            )

            approval_event = ApprovalEvent(
                response_id=status_activity_id,
                thread_id=original_message.get("message_id"),
                approver_email=supervisor_name,
                approved=True,
                approval_timestamp=datetime.now(),
                user_response_timestamp=datetime.now(),
                supervisor_message=supervisor_notes,
            )

            caddy.store_approver_event(
                original_message.get("message_id"), approval_event
            )

            response_card_body = self.messages.generate_response_card(llm_response)

            updated_response_card_body = (
                self.messages.update_response_card_with_supervisor_info(
                    response_card_body, supervisor_notes, supervisor_name
                )
            )

            self.update_status_card(
                caddy_message, status_activity_id, updated_response_card_body
            )

            approval_confirmation_card = (
                self.messages.create_approval_confirmation_card(
                    caddy_message, supervisor_notes, supervisor_name, llm_response
                )
            )
            self.update_card(event, card=approval_confirmation_card)

        except Exception as e:
            logger.error(f"Error in handle_approval: {str(e)}")
            raise

    def send_advisor_message_from_supervisor(self, event, text, type):
        """
        Sends a simple text message in response to an event.
        """
        if type == "donotshare":
            logger.info("No approval from supervisor")

        conversation_id = event["conversation"]["id"]
        service_url = event["serviceUrl"]

        response_url = f"{service_url}/v3/conversations/{conversation_id}/activities"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        response_activity = {
            "type": "message",
            "from": event["recipient"],
            "conversation": event["conversation"],
            "recipient": event["from"],
            "text": text,
        }

        response = requests.post(
            response_url, json=response_activity, headers=headers, timeout=60
        )

        logger.debug(response.json())

    def send_message_from_supervision_to_advisor(self, original_event, message):
        conversation_id = original_event["conversation"]["id"]
        service_url = original_event["serviceUrl"]

        response_url = f"{service_url}/v3/conversations/{conversation_id}/activities"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        response_activity = {
            "type": "message",
            "from": {"id": self.bot_id, "name": self.bot_name},
            "conversation": original_event["conversation"],
            "text": message,
        }

        try:
            response = requests.post(
                response_url, json=response_activity, headers=headers, timeout=60
            )
            response.raise_for_status()
            logger.debug(f"Message sent from supervision to advisor: {response.json()}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending message from supervision to advisor: {str(e)}")

    def handle_rejection(self, event):
        logger.info(f"Received rejection event: {json.dumps(event, indent=2)}")

        try:
            if "value" in event and isinstance(event["value"], dict):
                action_data = event["value"].get("action", {}).get("data", {})
            elif "data" in event:
                action_data = event["data"]
            else:
                action_data = event

            original_message = action_data.get("original_message", {})
            status_activity_id = action_data.get("status_activity_id", "")
            supervisor_notes = action_data.get("supervisorNotes", "")
            supervisor_name = event["from"]["name"]
            llm_response = action_data.get("llm_response", "")

            logger.debug(
                f"Extracted data: original_message={original_message}, supervisor_notes={supervisor_notes}, llm_response={llm_response}"
            )

            caddy_message = CaddyMessageEvent(
                type="REJECTED_MESSAGE",
                user=original_message.get("user"),
                name=original_message.get("name"),
                space_id=original_message.get("space_id"),
                message_id=original_message.get("message_id"),
                message_string=original_message.get("message_string"),
                source_client=self.client,
                timestamp=original_message.get("timestamp"),
                teams_conversation=original_message.get("teams_conversation"),
                teams_from=original_message.get("teams_from"),
                teams_recipient=original_message.get("teams_recipient"),
                teams_service_url=original_message.get("teams_service_url"),
            )

            rejection_event = ApprovalEvent(
                response_id=status_activity_id,
                thread_id=original_message.get("message_id"),
                approver_email=supervisor_name,
                approved=False,
                approval_timestamp=datetime.now(),
                user_response_timestamp=datetime.now(),
                supervisor_message=supervisor_notes,
            )

            caddy.store_approver_event(
                original_message.get("message_id"), rejection_event
            )

            rejection_card = self.messages.create_rejection_card(
                supervisor_notes, supervisor_name
            )

            self.update_status_card(caddy_message, status_activity_id, rejection_card)

            rejection_confirmation_card = (
                self.messages.create_rejection_confirmation_card(
                    caddy_message, supervisor_notes, supervisor_name, llm_response
                )
            )
            self.update_card(event, card=rejection_confirmation_card)

        except Exception as e:
            logger.error(f"Error in handle_rejection: {str(e)}")
            raise

    def send_status_update(
        self, event: CaddyMessageEvent, status: str, activity_id: str = None
    ):
        status_cards = {
            "processing": self.responses.PROCESSING_MESSAGE,
            "composing": self.responses.COMPOSING_MESSAGE,
            "composing_retry": self.responses.COMPOSING_RETRY,
            "request_failure": self.responses.REQUEST_FAILED,
            "supervisor_reviewing": self.responses.SUPERVISOR_REVIEWING,
            "awaiting_approval": self.responses.AWAITING_APPROVAL,
        }

        if status in status_cards:
            card_content = status_cards[status]

            if activity_id:
                return self.update_status_card(event, activity_id, card_content)
            else:
                return self.send_adviser_card(event, card_content)
        else:
            logger.error(f"Unknown status: {status}")
            return None

    def update_status_card(self, event, activity_id, card):
        conversation_id = event.teams_conversation["id"]
        service_url = event.teams_service_url

        response_url = (
            f"{service_url}/v3/conversations/{conversation_id}/activities/{activity_id}"
        )

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        response_activity = {
            "type": "message",
            "from": {"id": self.bot_id, "name": self.bot_name},
            "conversation": event.teams_conversation,
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": card,
                    },
                }
            ],
        }

        try:
            response = requests.put(
                response_url, json=response_activity, headers=headers, timeout=60
            )
            response.raise_for_status()
            logger.debug(f"Status card updated: {response.json()}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating status card: {str(e)}")
            logger.debug(f"Response content: {response.text}")
