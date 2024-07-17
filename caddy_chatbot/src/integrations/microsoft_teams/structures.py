from .verification import get_access_token

from integrations.microsoft_teams import content, responses
import requests

from caddy_core.services.anonymise import analyse

class MicrosoftTeams:
    def __init__(self):
        self.client = "Microsoft Teams"
        self.access_token = get_access_token()
        self.messages = content
        self.responses = responses

    def send_adviser_card(self, event, card = None):
        """
        Takes an incoming request from Teams Chat and returns a given response card
        """
        if card is None:
            card = self.messages.CADDY_PROCESSING
            
        conversation_id = event['conversation']['id']
        activity_id = event['id'] 
        service_url = event['serviceUrl']
        
        response_url = f"{service_url}/v3/conversations/{conversation_id}/activities/{activity_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response_activity = {
            "type": "message",
            "from": event['recipient'], 
            "conversation": event['conversation'],
            "recipient": event['from'], 
            "replyToId": activity_id,
            "attachments": [
                {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", 
                    "type": "AdaptiveCard", 
                    "version": "1.0", 
                    "body": card
                }
            }]
        }
        
        response = requests.post(
            response_url, 
            json=response_activity, 
            headers=headers
        )

        print(response.json())

    def update_card(self, event, card = None):
        """
        Updates an existing teams message given a card and action event
        """
        if card is None:
            card = self.messages.CADDY_PROCESSING
            
        conversation_id = event['conversation']['id']
        activity_id = event['id'] 
        service_url = event['serviceUrl']
        reply_to_id = event['replyToId']
        
        response_url = f"{service_url}/v3/conversations/{conversation_id}/activities/{reply_to_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response_activity = {
            "type": "message",
            "from": event['recipient'], 
            "conversation": event['conversation'],
            "recipient": event['from'], 
            "replyToId": activity_id,
            "attachments": [
                {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", 
                    "type": "AdaptiveCard", 
                    "version": "1.0", 
                    "body": card
                }
            }]
        }
        
        response = requests.put(
            response_url, 
            json=response_activity, 
            headers=headers
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
            
        self.send_adviser_card(event)

        # TODO Format Message into Caddy event
        return message_string