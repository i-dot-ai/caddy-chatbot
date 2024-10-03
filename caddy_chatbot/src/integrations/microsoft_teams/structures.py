import os
import json
import requests
from caddy_core.models import CaddyMessageEvent
from caddy_core.utils.monitoring import logger
from caddy_core.services.anonymise import analyse
from integrations.microsoft_teams import content, responses
from datetime import datetime

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

        print(response.json())

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

        print(response.json())

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

    def send_to_supervision(self, caddy_message, llm_response, context_sources):
        supervision_card = self.messages.create_supervision_card(
            caddy_message, llm_response, context_sources
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
            print(f"Supervision message sent: {response.json()}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending supervision message: {str(e)}")
            print(f"Response content: {response.text}")

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

            logger.debug(
                f"Extracted data: original_message={original_message}, llm_response={llm_response}, context_sources={context_sources}"
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

            response_card = self.messages.generate_response_card(llm_response)

            self.send_adviser_card(event=caddy_message, card=response_card)

            approval_confirmation_card = (
                self.messages.create_approval_confirmation_card(caddy_message)
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
            print("No approval from supervisor")

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

        print(response.json())

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
            print(f"Message sent from supervision to advisor: {response.json()}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending message from supervision to advisor: {str(e)}")

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

            logger.debug(f"Extracted data: original_message={original_message}")

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

            rejection_card = self.messages.create_rejection_card()

            self.send_adviser_card(event=caddy_message, card=rejection_card)

            rejection_confirmation_card = (
                self.messages.create_rejection_confirmation_card(caddy_message)
            )
            self.update_card(event, card=rejection_confirmation_card)

        except Exception as e:
            logger.error(f"Error in handle_rejection: {str(e)}")
            raise
