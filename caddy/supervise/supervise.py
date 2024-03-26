from caddy.events import (
    receive_new_ai_response,
    received_approval,
    received_rejection,
    get_user_details,
    add_user,
    remove_user,
    list_users,
    get_supervisor_response,
    introduce_caddy_supervisor,
)
from caddy.utils.core import helper_dialog
from caddy.services import enrolment
from integrations.google_chat.core import GoogleChat
import json


def lambda_handler(event, context):
    if "type" in event and event["type"] == "SUPERVISION_REQUIRED":
        receive_new_ai_response(event)

    chat_client = ""

    # --- Determine the chat client ---
    if "common" in event and event["common"]["hostApp"] == "CHAT":
        chat_client = "Google Chat"
    elif "type" in event and event["type"] == "ADDED_TO_SPACE":
        chat_client = "Google Chat"
    elif "channelId" in event and event["channelId"] == "msteams":
        chat_client = "Microsoft Teams"
    elif "source" in event and event["source"] == "CADDY_LOCAL":
        """
        TEST RUNNER FOR LOCAL SAM TESTING OF PLATFORM AGNOSTIC CADDY COMPONENTS
        """
        chat_client = "Caddy Local"

    match chat_client:
        case "Google Chat":
            """
            Handles inbound requests from Google Chat
            """
            google_chat = GoogleChat()
            user = event["user"]["email"]
            domain = user.split("@")[1]

            domain_enrolled = enrolment.check_domain_status(domain)
            if domain_enrolled is not True:
                return google_chat.messages["domain_not_enrolled"]

            user_enrolled = enrolment.check_user_status(user)
            if user_enrolled is not True:
                return google_chat.messages["user_not_registered"]

            match event["type"]:
                case "CARD_CLICKED":
                    match event["action"]["actionMethodName"]:
                        case "Approved":
                            received_approval(event)
                        case "rejected_dialog":
                            return get_supervisor_response(event)
                        case "receiveSupervisorResponse":
                            received_rejection(event)
                        case "receiveDialog":
                            match event["message"]["annotations"][0]["slashCommand"][
                                "commandName"
                            ]:
                                case "/addUser":
                                    return add_user(event)
                                case "/removeUser":
                                    return remove_user(event)
                case "MESSAGE":
                    match event["dialogEventType"]:
                        case "REQUEST_DIALOG":
                            match event["message"]["annotations"][0]["slashCommand"][
                                "commandName"
                            ]:
                                case "/addUser":
                                    return get_user_details("Add")
                                case "/removeUser":
                                    return get_user_details("Remove")
                                case "/listUsers":
                                    return list_users(event)
                                case "/help":
                                    return helper_dialog()
                case "ADDED_TO_SPACE":
                    return introduce_caddy_supervisor(event)
        case "Microsoft Teams":
            """
            TODO - Add Microsoft Teams support
            """
            return json.dumps(
                {"text": "Caddy is not currently available for this platform."}
            )
        case "Caddy Local":
            """
            TODO - SPLIT INTO PLATFORM AGNOSTIC CADDY COMPONENTS
            """
            user = event["user"]
            domain = user.split("@")[1]

            domain_enrolled = enrolment.check_domain_status(domain)
            if domain_enrolled is not True:
                return json.dumps(
                    {
                        "text": "Your domain is not enrolled in Caddy. Please contact your administrator."
                    }
                )

            user_enrolled = enrolment.check_user_status(user)
            if user_enrolled is not True:
                return json.dumps(
                    {
                        "text": "User is not registered, please contact your administrator for support in onboarding to Caddy"
                    }
                )

            return "Supervision Event Received"
        case _:
            return json.dumps(
                {"text": "Caddy is not currently available for this platform."}
            )
