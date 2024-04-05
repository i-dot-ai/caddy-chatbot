import json

from caddy import core as caddy
from caddy.services import enrolment

from integrations.google_chat.core import GoogleChat


def lambda_handler(event, context):
    chat_client = ""
    user = None

    # --- Determine the chat client ---
    if "type" in event and event["type"] == "SUPERVISION_REQUIRED":
        match event["source_client"]:
            case "Google Chat":
                chat_client = "Google Chat"
                user = event["user"]
            case "Microsoft Teams":
                chat_client = "Microsoft Teams"
            case "CADDY_LOCAL":
                chat_client = "Caddy Local"
    elif "common" in event and event["common"]["hostApp"] == "CHAT":
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
            user = user or event["user"]["email"]
            domain = user.split("@")[1]

            domain_enrolled = enrolment.check_domain_status(domain)
            if domain_enrolled is not True:
                return google_chat.messages["domain_not_enrolled"]

            user_enrolled = enrolment.check_user_status(user)
            if user_enrolled is not True:
                return google_chat.messages["user_not_registered"]

            match event["type"]:
                case "ADDED_TO_SPACE":
                    match event["space"]["type"]:
                        case "DM":
                            return google_chat.messages["introduce_caddy_supervisor_DM"]
                        case "ROOM":
                            return json.dumps(
                                {
                                    "text": google_chat.messages[
                                        "introduce_caddy_supervisor_SPACE"
                                    ].format(space=event["space"]["displayName"])
                                }
                            )
                case "SUPERVISION_REQUIRED":
                    supervisor_space = enrolment.get_designated_supervisor_space(user)

                    if supervisor_space == "Unknown":
                        raise Exception("supervision space returned unknown")

                    google_chat.handle_new_supervision_event(
                        user, supervisor_space, event
                    )

                    caddy.store_approver_received_timestamp(event)
                case "CARD_CLICKED":
                    match event["action"]["actionMethodName"]:
                        case "Approved":
                            (
                                user,
                                user_space,
                                thread_id,
                                approval_event,
                            ) = google_chat.received_approval(event)
                            caddy.store_approver_event(approval_event)

                            google_chat.call_complete_confirmation(user, user_space, thread_id)
                        case "rejected_dialog":
                            return google_chat.get_supervisor_response(event)
                        case "receiveSupervisorResponse":
                            (
                                confirmation_of_receipt,
                                user,
                                user_space,
                                thread_id,
                                rejection_event,
                            ) = google_chat.received_rejection(event)

                            caddy.store_approver_event(rejection_event)
                            
                            google_chat.call_complete_confirmation(user, user_space, thread_id)

                            return confirmation_of_receipt
                        case "receiveDialog":
                            match event["message"]["annotations"][0]["slashCommand"][
                                "commandName"
                            ]:
                                case "/addUser":
                                    return google_chat.add_user(event)
                                case "/removeUser":
                                    return google_chat.remove_user(event)
                case "MESSAGE":
                    match event["dialogEventType"]:
                        case "REQUEST_DIALOG":
                            match event["message"]["annotations"][0]["slashCommand"][
                                "commandName"
                            ]:
                                case "/addUser":
                                    return google_chat.get_user_details("Add")
                                case "/removeUser":
                                    return google_chat.get_user_details("Remove")
                                case "/listUsers":
                                    return google_chat.list_space_users(event)
                                case "/help":
                                    return google_chat.helper_dialog()
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
