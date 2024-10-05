import os
import json
import aiohttp
import asyncio
from caddy_core.models import (
    CaddyMessageEvent,
    ApprovalEvent,
    UserNotEnrolledException,
    NoSupervisionSpaceException,
)
from caddy_core.utils.monitoring import logger
from caddy_core.services.anonymise import analyse
from integrations.microsoft_teams import content, responses
from datetime import datetime

from caddy_core import components as caddy

from caddy_core.services import enrolment

from .verification import get_access_token, get_graph_access_token


async def initialise_teams_client(event):
    user_id = event["from"]["aadObjectId"]
    user_enrolled, user_record = enrolment.check_user_status(user_id)
    user_supervisor = enrolment.check_user_role(user_record)

    if not user_enrolled:
        logger.debug("User is not enrolled")
        raise UserNotEnrolledException("User is not enrolled in Caddy.")

    logger.debug("User is enrolled")

    supervision_space_id = user_record.get("supervisionSpaceId")
    if not supervision_space_id:
        logger.error("No supervision space found for user")
        raise NoSupervisionSpaceException("No supervision space found for user.")

    service_url = event["serviceUrl"]
    tenant_id = event["conversation"]["tenantId"]

    return (
        MicrosoftTeams(
            supervision_space_id=supervision_space_id,
            service_url=service_url,
            tenant_id=tenant_id,
        ),
        user_supervisor,
    )


class MicrosoftTeams:
    def __init__(self, supervision_space_id=None, service_url=None, tenant_id=None):
        self.client = "Microsoft Teams"
        self.access_token = get_access_token()
        self.messages = content
        self.responses = responses
        self.bot_id = os.getenv("TEAMS_BOT_ID")
        self.bot_name = "Caddy"
        self.supervision_space_id = supervision_space_id
        self.service_url = service_url
        self.tenant_id = tenant_id

    async def handle_message_event(self, event, user_supervisor):
        conversation_id = event["conversation"]["id"]

        if event.get("text"):
            command = event["text"].lower().strip()
            return await self.process_command(
                command, event, user_supervisor, conversation_id
            )
        elif event.get("value"):
            return await self.process_user_management_action(
                event, user_supervisor, conversation_id
            )
        else:
            logger.warning("Received message event without text or value")
            return self.responses.OK

    async def handle_invoke_event(self, event, user_supervisor):
        conversation_id = event["conversation"]["id"]

        match event.get("name"):
            case "adaptiveCard/action":
                return await self.handle_adaptive_card_action(event, user_supervisor)
            case "addUser" | "removeUser" | "listUsers" | "help":
                if not user_supervisor:
                    await self.send_unauthorised_access_message(conversation_id)
                    return self.responses.OK

                match event["name"]:
                    case "addUser":
                        await self.get_add_user_dialog(conversation_id)
                    case "removeUser":
                        await self.get_remove_user_dialog(conversation_id)
                    case "listUsers":
                        await self.list_space_users(conversation_id)
                    case "help":
                        await self.get_help_card(conversation_id)
                return self.responses.OK
            case _:
                logger.warning(f"Unhandled invoke name: {event.get('name')}")
                return self.responses.OK

    async def handle_adaptive_card_action(self, event, user_supervisor):
        if not user_supervisor:
            conversation_id = event["conversation"]["id"]
            await self.send_unauthorised_access_message(conversation_id)
            return self.responses.OK

        action_data = event["value"]["action"]["data"]
        action = action_data["action"]

        match action:
            case "approved":
                await self.handle_approval(event)
            case "rejected":
                await self.handle_rejection(event)
            case _:
                logger.warning(f"Unhandled adaptive card action: {action}")

        return self.responses.OK

    async def process_command(self, command, event, user_supervisor, conversation_id):
        command = command.replace("<at>caddy</at>", "").strip()

        match command.split()[0]:
            case "adduser":
                return await self.handle_supervisor_command(
                    self.get_add_user_dialog, user_supervisor, conversation_id
                )
            case "removeuser":
                return await self.handle_supervisor_command(
                    self.get_remove_user_dialog, user_supervisor, conversation_id
                )
            case "listusers":
                return await self.handle_supervisor_command(
                    self.list_space_users, user_supervisor, conversation_id
                )
            case "help":
                await self.get_help_card(conversation_id)
                return self.responses.OK
            case _:
                return await self.process_caddy_message(event)

    async def handle_supervisor_command(
        self, command_func, user_supervisor, conversation_id
    ):
        if not user_supervisor:
            await self.send_unauthorised_access_message(conversation_id)
            return self.responses.OK
        await command_func(conversation_id)
        return self.responses.OK

    async def process_caddy_message(self, event):
        caddy_message = await self.format_message(event)
        if caddy_message != "PII Detected":
            await caddy.temporary_teams_invoke(self, caddy_message)
        return self.responses.OK

    async def process_user_management_action(
        self, event, user_supervisor, conversation_id
    ):
        if not user_supervisor:
            await self.send_unauthorised_access_message(conversation_id)
            return self.responses.OK

        action = event["value"].get("action")
        match action:
            case "addUser":
                await self.add_user(event)
            case "removeUser":
                await self.remove_user(event)
            case _:
                logger.warning(f"Unhandled value action: {action}")

        return self.responses.OK

    async def send_card_to_chat(self, conversation_id: str, card: dict):
        url = f"{self.service_url}/v3/conversations/{conversation_id}/activities"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        body = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
                response_text = await response.text()
                if response.status in [200, 201]:
                    logger.debug(f"Card sent successfully: {response_text}")
                    return json.loads(response_text)
                else:
                    logger.error(
                        f"Failed to send card. Status: {response.status}, Response: {response_text}"
                    )
                    return None

    async def get_tenant_users(self):
        logger.debug(f"Fetching users for tenant: {self.tenant_id}")
        url = "https://graph.microsoft.com/v1.0/users"
        graph_token = get_graph_access_token(self.tenant_id)

        if not graph_token:
            logger.error("Failed to obtain Graph API token")
            return []

        headers = {
            "Authorization": f"Bearer {graph_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status in [200, 201]:
                        users = await response.json()
                        return [
                            {
                                "title": user["displayName"],
                                "value": json.dumps(
                                    {
                                        "id": user["id"],
                                        "friendlyName": user["displayName"],
                                    }
                                ),
                            }
                            for user in users["value"]
                        ]
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to fetch tenant users. Status: {response.status}, Response: {error_text}"
                        )
                        logger.error(f"Request URL: {url}")
                        logger.error(f"Request Headers: {headers}")
                        return []
            except Exception as e:
                logger.error(f"Error fetching tenant users: {str(e)}")
                return []

    async def get_add_user_dialog(self, conversation_id: str):
        users = await self.get_tenant_users()

        card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Add a new user to Caddy",
                    "weight": "Bolder",
                    "size": "Medium",
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "teamsUser",
                    "label": "Select user",
                    "choices": users,
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "role",
                    "label": "User's role",
                    "choices": [
                        {"title": "Adviser", "value": "Adviser"},
                        {"title": "Supervisor", "value": "Supervisor"},
                    ],
                },
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Add User",
                    "data": {"action": "addUser"},
                }
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2",
        }
        await self.send_card_to_chat(conversation_id, card)

    async def get_user_details(self, user_id: str):
        url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
        graph_token = get_graph_access_token(self.tenant_id)
        headers = {
            "Authorization": f"Bearer {graph_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status in [200, 201]:
                        user_details = await response.json()
                        return {
                            "displayName": user_details.get(
                                "displayName", "Unknown User"
                            ),
                            "userPrincipalName": user_details.get(
                                "userPrincipalName", ""
                            ),
                        }
                    else:
                        logger.error(
                            f"Failed to fetch user details. Status: {response.status}"
                        )
                        return {"displayName": "Unknown User", "userPrincipalName": ""}
            except Exception as e:
                logger.error(f"Error fetching user details: {str(e)}")
                return {"displayName": "Unknown User", "userPrincipalName": ""}

    async def get_conversation_members(self, conversation_id: str):
        url = f"{self.service_url}/v3/conversations/{conversation_id}/members"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status in [200, 201]:
                        members = await response.json()
                        logger.debug(
                            f"Successfully fetched {len(members)} conversation members"
                        )
                        return members
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to fetch conversation members. Status: {response.status}, Response: {error_text}"
                        )
                        return []
            except aiohttp.ClientError as e:
                logger.error(
                    f"Network error while fetching conversation members: {str(e)}"
                )
                return []
            except asyncio.TimeoutError:
                logger.error("Timeout while fetching conversation members")
                return []
            except Exception as e:
                logger.error(
                    f"Unexpected error while fetching conversation members: {str(e)}"
                )
                return []

    async def get_team_members(self, team_id: str):
        url = f"{self.service_url}/v3/teams/{team_id}/members"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status in [200, 201]:
                        members = await response.json()
                        logger.debug(
                            f"Successfully fetched {len(members)} team members"
                        )
                        return members
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to fetch team members. Status: {response.status}, Response: {error_text}"
                        )
                        return []
            except aiohttp.ClientError as e:
                logger.error(f"Network error while fetching team members: {str(e)}")
                return []
            except asyncio.TimeoutError:
                logger.error("Timeout while fetching team members")
                return []
            except Exception as e:
                logger.error(f"Unexpected error while fetching team members: {str(e)}")
                return []

    async def send_adviser_card(self, event: CaddyMessageEvent, card=None):
        if card is None:
            card = self.messages.CADDY_PROCESSING

        conversation_id = event.teams_conversation["id"]
        activity_id = event.message_id

        response_url = f"{self.service_url}/v3/conversations/{conversation_id}/activities/{activity_id}"

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

        async with aiohttp.ClientSession() as session:
            async with session.post(
                response_url, json=response_activity, headers=headers, timeout=60
            ) as response:
                response_json = await response.json()
                logger.debug(response_json)
                return response_json.get("id")

    async def update_card(self, event, card):
        conversation_id = event["conversation"]["id"]
        activity_id = event["replyToId"]

        url = f"{self.service_url}/v3/conversations/{conversation_id}/activities/{activity_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        body = {
            "type": "message",
            "id": activity_id,
            "conversation": {"id": conversation_id},
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.put(url, headers=headers, json=body) as response:
                    if response.status not in [200, 201]:
                        logger.error(f"Failed to update card: {await response.text()}")
                    else:
                        logger.debug(
                            f"Card updated successfully: {await response.text()}"
                        )
            except Exception as e:
                logger.error(f"Error updating card: {str(e)}")

    async def update_add_user_card(self, event, status_message, status_color):
        card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Add a new user to Caddy",
                    "weight": "Bolder",
                    "size": "Medium",
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "teamsUser",
                    "label": "Select user",
                    "choices": await self.get_tenant_users(),
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "role",
                    "label": "User's role",
                    "choices": [
                        {"title": "Adviser", "value": "Adviser"},
                        {"title": "Supervisor", "value": "Supervisor"},
                    ],
                },
                {
                    "type": "TextBlock",
                    "text": status_message,
                    "wrap": True,
                    "color": status_color,
                },
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Add User",
                    "data": {"action": "addUser"},
                }
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2",
        }

        await self.update_card(event, card)

    async def format_message(self, event):
        message_string = event["text"].replace("<at>Caddy</at>", "").strip()

        if "proceed" not in event:
            pii_identified = analyse(message_string)

            if pii_identified:
                # Optionally redact PII from the message by importing redact from services.anonymise
                # message_string = redact(message_string, pii_identified)

                await self.send_adviser_card(
                    event=event,
                    card=self.messages.create_pii_detected_card(message_string),
                )
                return "PII Detected"

        caddy_message = CaddyMessageEvent(
            type="PROCESS_CHAT_MESSAGE",
            user=event["from"]["aadObjectId"],
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

    async def send_to_supervision(
        self, caddy_message, llm_response, context_sources, status_activity_id
    ):
        supervision_card = self.messages.create_supervision_card(
            caddy_message, llm_response, context_sources, status_activity_id
        )

        response_url = f"{self.service_url}/v3/conversations/{self.supervision_space_id}/activities"

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

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    response_url, json=response_activity, headers=headers, timeout=60
                ) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    logger.debug(f"Supervision message sent: {response_json}")
            except aiohttp.ClientError as e:
                logger.error(f"Error sending supervision message: {str(e)}")

    async def handle_approval(self, event):
        logger.debug(f"Received approval event: {json.dumps(event, indent=2)}")

        try:
            action_data = event["value"]["action"]["data"]

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

            await self.update_status_card(
                caddy_message, status_activity_id, updated_response_card_body
            )

            approval_confirmation_card = (
                self.messages.create_approval_confirmation_card(
                    caddy_message, supervisor_notes, supervisor_name, llm_response
                )
            )
            await self.update_card(event, card=approval_confirmation_card)

        except Exception as e:
            logger.error(f"Error in handle_approval: {str(e)}")
            raise

    async def handle_rejection(self, event):
        logger.debug(f"Received rejection event: {json.dumps(event, indent=2)}")

        try:
            action_data = event["value"]["action"]["data"]

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
                supervisor_name, supervisor_notes
            )

            await self.update_status_card(
                caddy_message, status_activity_id, rejection_card
            )

            rejection_confirmation_card = (
                self.messages.create_rejection_confirmation_card(
                    caddy_message, supervisor_notes, supervisor_name, llm_response
                )
            )
            await self.update_card(event, card=rejection_confirmation_card)

        except Exception as e:
            logger.error(f"Error in handle_rejection: {str(e)}")
            raise

    async def update_status_card(self, event, activity_id, card):
        conversation_id = event.teams_conversation["id"]

        response_url = f"{self.service_url}/v3/conversations/{conversation_id}/activities/{activity_id}"

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

        async with aiohttp.ClientSession() as session:
            try:
                async with session.put(
                    response_url, json=response_activity, headers=headers, timeout=60
                ) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    logger.debug(f"Status card updated: {response_json}")
            except aiohttp.ClientError as e:
                logger.error(f"Error updating status card: {str(e)}")

    async def get_remove_user_dialog(self, conversation_id: str):
        tenant_users = await self.get_tenant_users()

        enrolled_users = enrolment.list_users(conversation_id, ids_only=True)

        enrolled_user_dict = {}
        for user in tenant_users:
            user_data = json.loads(user["value"])
            if user_data["id"] in enrolled_users:
                enrolled_user_dict[user_data["id"]] = user_data["friendlyName"]

        choices = [
            {"title": name, "value": json.dumps({"id": id, "friendlyName": name})}
            for id, name in enrolled_user_dict.items()
        ]

        card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Remove a user from Caddy",
                    "weight": "Bolder",
                    "size": "Medium",
                },
                (
                    {
                        "type": "Input.ChoiceSet",
                        "id": "teamsUser",
                        "label": "Select user to remove",
                        "choices": choices,
                    }
                    if choices
                    else {
                        "type": "TextBlock",
                        "text": "No enrolled users found.",
                        "color": "Attention",
                    }
                ),
            ],
            "actions": (
                [
                    {
                        "type": "Action.Submit",
                        "title": "Remove User",
                        "data": {"action": "removeUser"},
                    }
                ]
                if choices
                else []
            ),
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2",
        }
        await self.send_card_to_chat(conversation_id, card)

    async def update_remove_user_card(self, event, status_message, status_color):
        tenant_users = await self.get_tenant_users()
        conversation_id = event["conversation"]["id"]

        enrolled_users = enrolment.list_users(conversation_id, ids_only=True)

        enrolled_user_dict = {}
        for user in tenant_users:
            user_data = json.loads(user["value"])
            if user_data["id"] in enrolled_users:
                enrolled_user_dict[user_data["id"]] = user_data["friendlyName"]

        choices = [
            {"title": name, "value": json.dumps({"id": id, "friendlyName": name})}
            for id, name in enrolled_user_dict.items()
        ]

        card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Remove a user from Caddy",
                    "weight": "Bolder",
                    "size": "Medium",
                },
                (
                    {
                        "type": "Input.ChoiceSet",
                        "id": "teamsUser",
                        "label": "Select user to remove",
                        "choices": choices,
                    }
                    if choices
                    else {
                        "type": "TextBlock",
                        "text": "No enrolled users found.",
                        "color": "Attention",
                    }
                ),
                {
                    "type": "TextBlock",
                    "text": status_message,
                    "wrap": True,
                    "color": status_color,
                },
            ],
            "actions": (
                [
                    {
                        "type": "Action.Submit",
                        "title": "Remove User",
                        "data": {"action": "removeUser"},
                    }
                ]
                if choices
                else []
            ),
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2",
        }

        await self.update_card(event, card)

    async def add_user(self, event):
        user_data = json.loads(event["value"]["teamsUser"])
        teams_user_id = user_data["id"]
        role = event["value"]["role"]
        user_name = user_data["friendlyName"]
        conversation_id = event["conversation"]["id"]

        try:
            result = enrolment.register_user(
                teams_user_id, role, conversation_id, user_name
            )
            if result["status"] == 200:
                status_message = f"{user_name} added successfully as {role}"
                status_color = "Good"
            else:
                raise Exception(result["content"])
        except Exception as error:
            status_message = f"Failed to add user: {str(error)}"
            status_color = "Attention"

        await self.update_add_user_card(event, status_message, status_color)

    async def remove_user(self, event):
        user_data = json.loads(event["value"]["teamsUser"])
        user_id = user_data["id"]
        user_name = user_data["friendlyName"]

        try:
            enrolment.remove_user(user_id)
            status_message = f"{user_name} removed successfully"
            status_color = "Good"
        except Exception as error:
            status_message = f"Failed to remove user: {str(error)}"
            status_color = "Attention"

        await self.update_remove_user_card(event, status_message, status_color)

    async def list_space_users(self, conversation_id: str):
        try:
            users = enrolment.list_users(conversation_id, display_names=True)
            logger.debug(f"USERS: {users}")
            user_list = "\n".join(users) if users else "No users found."

            card = {
                "type": "AdaptiveCard",
                "body": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "Image",
                                        "url": "https://storage.googleapis.com/sort_assets/groups.png",
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
                                        "text": "Registered Users",
                                        "weight": "Bolder",
                                        "size": "Medium",
                                        "spacing": "None",
                                    },
                                ],
                                "verticalContentAlignment": "Center",
                            },
                        ],
                        "spacing": "Small",
                    },
                    {"type": "TextBlock", "text": user_list, "wrap": True},
                ],
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "version": "1.2",
            }
            result = await self.send_card_to_chat(conversation_id, card)
            if result:
                logger.debug(f"List users card sent successfully: {result}")
            else:
                logger.error("Failed to send list users card")
        except Exception as error:
            logger.error(f"Error in list_space_users: {str(error)}")
            error_card = {
                "type": "AdaptiveCard",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": f"Failed to list users: {str(error)}",
                        "wrap": True,
                        "color": "Attention",
                    }
                ],
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "version": "1.2",
            }
            await self.send_card_to_chat(conversation_id, error_card)

    async def get_help_card(self, conversation_id: str):
        card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Caddy Supervision Commands",
                    "weight": "Bolder",
                    "size": "Medium",
                },
                {
                    "type": "TextBlock",
                    "text": "• addUser: Add a new user to Caddy\n• removeUser: Remove a user from Caddy\n• listUsers: List all users in the supervision space\n• help: Display this help information",
                    "wrap": True,
                },
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2",
        }
        await self.send_card_to_chat(conversation_id, card)

    async def send_status_update(
        self, event: CaddyMessageEvent, status: str, activity_id: str = None
    ):
        status_cards = {
            "processing": self.responses.PROCESSING_MESSAGE,
            "composing": self.responses.COMPOSING_MESSAGE,
            "composing_retry": self.responses.COMPOSING_RETRY,
            "request_failure": self.responses.REQUEST_FAILED,
            "supervisor_reviewing": self.responses.SUPERVISOR_REVIEWING,
            "awaiting_approval": self.responses.AWAITING_APPROVAL,
            "unauthorised_supervision": self.responses.UNAUTHORISED_SUPERVISOR_ACCESS,
        }

        if status in status_cards:
            card_content = status_cards[status]

            if activity_id:
                return await self.update_status_card(event, activity_id, card_content)
            else:
                return await self.send_adviser_card(event, card_content)
        else:
            logger.error(f"Unknown status: {status}")
            return None

    async def send_unauthorised_access_message(self, conversation_id):
        response_url = (
            f"{self.service_url}/v3/conversations/{conversation_id}/activities"
        )

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        response_activity = {
            "type": "message",
            "from": {"id": self.bot_id, "name": self.bot_name},
            "conversation": {"id": conversation_id},
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": self.responses.UNAUTHORISED_SUPERVISOR_ACCESS,
                    },
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    response_url, json=response_activity, headers=headers, timeout=60
                ) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    logger.debug(f"Unauthorized access message sent: {response_json}")
            except aiohttp.ClientError as e:
                logger.error(f"Error sending unauthorized access message: {str(e)}")
