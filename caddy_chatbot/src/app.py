from fastapi import FastAPI, Depends, Request, status
from fastapi.responses import JSONResponse, Response

from caddy_core import components as caddy
from caddy_core.services import enrolment

from integrations.google_chat.structures import GoogleChat
from integrations.google_chat.verification import (
    verify_google_chat_request,
    verify_google_chat_supervision_request,
)

import pyperclip

from threading import Thread

app = FastAPI(docs_url=None)


@app.get("/health")
def health():
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "Online"})


@app.post("/google-chat/chat")
def google_chat_endpoint(event=Depends(verify_google_chat_request)) -> dict:
    """
    Handles inbound requests from Google Chat for Caddy
    """
    google_chat = GoogleChat()
    user = event["user"]["email"]
    domain = user.split("@")[1]

    domain_enrolled, office = enrolment.check_domain_status(domain)
    if domain_enrolled is not True:
        return google_chat.responses.DOMAIN_NOT_ENROLLED

    user_enrolled, user_record = enrolment.check_user_status(user)
    if user_enrolled is not True:
        return google_chat.responses.USER_NOT_ENROLLED

    included_in_rct = enrolment.check_rct_status(office)
    if included_in_rct is True:
        user_has_existing_call = enrolment.check_user_call_status(user_record)
        if user_has_existing_call is True and event["type"] == "MESSAGE":
            caddy.rct_survey_reminder(event, user_record, chat_client=google_chat)
            return google_chat.responses.NO_CONTENT

    match event["type"]:
        case "ADDED_TO_SPACE":
            match event["space"]["type"]:
                case "DM":
                    return google_chat.responses.INTRODUCE_CADDY_IN_DM
                case "ROOM":
                    return google_chat.responses.introduce_caddy_in_space(
                        space_name=event["space"]["displayName"]
                    )
        case "MESSAGE":
            caddy_message = google_chat.format_message(event)
            if caddy_message == "PII Detected":
                return google_chat.responses.NO_CONTENT
            process_message_thread = Thread(
                target=caddy.handle_message,
                kwargs={"caddy_message": caddy_message, "chat_client": google_chat},
            )
            process_message_thread.start()
            return google_chat.responses.ACCEPTED
        case "CARD_CLICKED":
            match event["action"]["actionMethodName"]:
                case "Proceed":
                    caddy_message = google_chat.handle_proceed_query(event)
                    process_message_thread = Thread(
                        target=caddy.handle_message,
                        kwargs={
                            "caddy_message": caddy_message,
                            "chat_client": google_chat,
                        },
                    )
                    process_message_thread.start()
                    return google_chat.responses.NO_CONTENT
                case "handle_control_group_forward":
                    caddy_message = google_chat.handle_control_group_query(event)
                    control_group_card = {"cardsV2": event["message"]["cardsV2"]}
                    control_group_card["cardsV2"][0]["card"]["sections"][0][
                        "widgets"
                    ].pop()
                    control_group_card["cardsV2"][0]["card"]["sections"][0][
                        "widgets"
                    ].append(
                        {
                            "textParagraph": {
                                "text": '<font color="#005743"><b>Request forwarded to supervisor<b></font>'
                            }
                        }
                    )
                    supervisor_space = enrolment.get_designated_supervisor_space(
                        caddy_message.user
                    )
                    google_chat.send_message_to_supervisor_space(
                        space_id=supervisor_space,
                        message=google_chat.responses.message_control_forward(
                            caddy_message.user, caddy_message.message_string
                        ),
                    )
                    control_group_card = google_chat.append_survey_questions(
                        control_group_card, caddy_message.thread_id, caddy_message.user
                    )
                    google_chat.update_message_in_adviser_space(
                        message_type="cardsV2",
                        space_id=caddy_message.space_id,
                        message_id=caddy_message.message_id,
                        message=control_group_card,
                    )
                    return google_chat.responses.NO_CONTENT
                case "control_group_survey":
                    caddy_message = google_chat.handle_control_group_query(event)
                    control_group_card = {"cardsV2": event["message"]["cardsV2"]}
                    control_group_card["cardsV2"][0]["card"]["sections"][0][
                        "widgets"
                    ].pop()
                    control_group_card = google_chat.append_survey_questions(
                        control_group_card, caddy_message.thread_id, caddy_message.user
                    )
                    google_chat.update_message_in_adviser_space(
                        message_type="cardsV2",
                        space_id=caddy_message.space_id,
                        message_id=caddy_message.message_id,
                        message=control_group_card,
                    )
                    return google_chat.responses.NO_CONTENT
                case "edit_query_dialog":
                    return google_chat.get_edit_query_dialog(event)
                case "receiveEditedQuery":
                    caddy_message = google_chat.handle_edited_query(event)
                    process_message_thread = Thread(
                        target=caddy.handle_message,
                        kwargs={
                            "caddy_message": caddy_message,
                            "chat_client": google_chat,
                        },
                    )
                    process_message_thread.start()
                    return google_chat.responses.SUCCESS_DIALOG
                case "continue_existing_interaction":
                    google_chat.continue_existing_interaction(event)
                    caddy_message = google_chat.handle_proceed_query(event)
                    process_message_thread = Thread(
                        target=caddy.handle_message,
                        kwargs={
                            "caddy_message": caddy_message,
                            "chat_client": google_chat,
                        },
                    )
                    process_message_thread.start()
                    return google_chat.responses.NO_CONTENT
                case "end_existing_interaction":
                    google_chat.end_existing_interaction(event)
                    return google_chat.responses.NO_CONTENT
                case "copy_caddy_response":
                    pyperclip.copy(event["common"]["parameters"]["aiResponse"])
                case "survey_response":
                    message_event = google_chat.handle_survey_response(event)
                    if message_event:
                        event["message"]["text"] = message_event
                        caddy_message = google_chat.format_message(event)
                        process_message_thread = Thread(
                            target=caddy.handle_message,
                            kwargs={
                                "caddy_message": caddy_message,
                                "chat_client": google_chat,
                            },
                        )
                        process_message_thread.start()
                    return google_chat.responses.ACCEPTED
                case "call_complete":
                    google_chat.finalise_caddy_call(event)
                    return google_chat.responses.ACCEPTED
        case _:
            return Response(status_code=status.HTTP_404_NOT_FOUND)


@app.post("/google-chat/supervision")
def google_chat_supervision_endpoint(
    event=Depends(verify_google_chat_supervision_request),
):
    """
    Handles inbound requests from Google Chat for Caddy Supervisor
    """
    google_chat = GoogleChat()
    user = event["user"]["email"]
    domain = user.split("@")[1]

    domain_enrolled, _ = enrolment.check_domain_status(domain)
    if domain_enrolled is not True:
        return google_chat.responses.DOMAIN_NOT_ENROLLED

    user_enrolled, user_record = enrolment.check_user_status(user)
    if user_enrolled is not True:
        return google_chat.responses.USER_NOT_ENROLLED

    user_supervisor = enrolment.check_user_role(user_record)
    if user_supervisor is not True:
        return google_chat.responses.USER_NOT_SUPERVISOR

    match event["type"]:
        case "ADDED_TO_SPACE":
            match event["space"]["type"]:
                case "DM":
                    return google_chat.responses.INTRODUCE_CADDY_SUPERVISOR_IN_DM
                case "ROOM":
                    return google_chat.responses.introduce_caddy_supervisor_in_space(
                        space_name=event["space"]["displayName"]
                    )
        case "CARD_CLICKED":
            match event["action"]["actionMethodName"]:
                case "Approved":
                    google_chat.handle_supervisor_approval(event)
                    return google_chat.responses.NO_CONTENT
                case "Rejected":
                    google_chat.handle_supervisor_rejection(event)
                    return google_chat.responses.NO_CONTENT
                case "receiveDialog":
                    match event["message"]["annotations"][0]["slashCommand"][
                        "commandName"
                    ]:
                        case "/addUser":
                            google_chat.add_user(event)
                            return google_chat.responses.SUCCESS_DIALOG
                        case "/removeUser":
                            google_chat.remove_user(event)
                            return google_chat.responses.SUCCESS_DIALOG
        case "MESSAGE":
            match event["dialogEventType"]:
                case "REQUEST_DIALOG":
                    match event["message"]["annotations"][0]["slashCommand"][
                        "commandName"
                    ]:
                        case "/addUser":
                            return google_chat.responses.ADD_USER_DIALOG
                        case "/removeUser":
                            return google_chat.responses.REMOVE_USER_DIALOG
                        case "/help":
                            return google_chat.responses.HELPER_DIALOG
                        case "/listUsers":
                            return JSONResponse(
                                content=google_chat.list_space_users(event)
                            )
        case _:
            return Response(status_code=status.HTTP_404_NOT_FOUND)


@app.post("/microsoft-teams/chat")
def microsoft_teams_endpoint(request: Request):
    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"text": "Request received"}
    )


@app.post("/microsoft-teams/supervision")
def microsoft_teams_supervision_endpoint(request: Request):
    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"text": "Request received"}
    )


@app.post("/caddy/chat")
def caddy_endpoint(request: Request):
    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"text": "Request received"}
    )


@app.post("/caddy/supervision")
def caddy_supervision_endpoint(request: Request):
    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"text": "Request received"}
    )
