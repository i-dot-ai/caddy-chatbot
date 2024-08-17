from .verification import get_access_token
from integrations.microsoft_teams import content, responses
from caddy_core.services.anonymise import analyse

import requests


class MicrosoftTeams:
    def __init__(self):
        self.client = "Microsoft Teams"
        self.access_token = get_access_token()
        self.messages = content
        self.responses = responses
        self.reaction_actions = {
            "like": self.handle_thumbs_up,
            "dislike": self.handle_thumbs_down,
        }  # TODO check works in teams with the emojis

    def send_adviser_card(self, event, card=None):
        """
        Takes an incoming request from Teams Chat and returns a given response card
        """
        if card is None:
            card = self.messages.CADDY_PROCESSING

        conversation_id = event["conversation"]["id"]
        activity_id = event["id"]
        service_url = event["serviceUrl"]

        response_url = (
            f"{service_url}/v3/conversations/{conversation_id}/activities/{activity_id}"
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

        response = requests.post(response_url, json=response_activity, headers=headers)

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

        response = requests.put(response_url, json=response_activity, headers=headers)

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

        self.send_adviser_card(event)

        # TODO Format Message into Caddy event
        return message_string

    def handle_reaction_added(self, event):
        """
        Handles reactions added to a message, specifically for the sueprvisor space but currently applied to all
        """
        reaction_type = event["reactionsAdded"][0]["type"]
        reply_to_id = event["replyToId"]

        # Fetch original message or log activity based on reply_to_id if needed
        response_text = (
            f"Reaction '{reaction_type}' added to message with ID {reply_to_id}"
        )
        self.send_advisor_message_from_supervisor(event, response_text)

        # TODO define a send_advisor_message_from_supervisor methods
        # TODO return caddy message from supervisor channel to advisor

    def handle_reaction_removed(self, event):
        """
        Handles reactions removed from a message, currently unsure if we need this
        """
        reaction_type = event["reactionsRemoved"][0]["type"]
        reply_to_id = event["replyToId"]

        # Fetch original message or log activity based on reply_to_id if needed

        response_text = (
            f"Reaction '{reaction_type}' removed from message with ID {reply_to_id}"
        )
        self.send_advisor_message_from_supervisor(event, response_text)

    def handle_thumbs_up(self, event, removed=False):
        """
        Handle thumbs up reaction = an approval from supervisor
        """
        action = "removed" if removed else "added"
        self.send_advisor_message_from_supervisor(
            event,
            f"Message approved {action} for message with ID {event['replyToId']}",
            "share",
        )

    def handle_thumbs_down(self, event, removed=False):
        """
        Handle thumbs down reaction = no approval from supervisor, caddy message not sent
        """
        action = "removed" if removed else "added"
        self.send_advisor_message_from_supervisor(
            event,
            f"Answer not approved {action} for message with ID {event['replyToId']}",
            "donotshare",
        )

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

        response = requests.post(response_url, json=response_activity, headers=headers)

        print(response.json())

    # TODO make this have the details from caddy and the supervisor comments
