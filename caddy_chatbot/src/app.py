from fastapi import FastAPI, Depends, Request, status, BackgroundTasks
from fastapi.responses import JSONResponse, Response

from caddy_core import core as caddy
from caddy_core.services import enrolment
from integrations.google_chat.structures import GoogleChat

from integrations.google_chat.verification import (
    verify_google_chat_request,
    verify_google_chat_supervision_request,
)

app = FastAPI(docs_url=None)


@app.get("/health")
def health():
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "Online"})


@app.post("/google-chat/chat")
async def google_chat_endpoint(
    background_tasks: BackgroundTasks, event=Depends(verify_google_chat_request)
) -> dict:
    """
    Handles inbound requests from Google Chat for Caddy
    """
    google_chat = GoogleChat()
    user = event["user"]["email"]
    domain = user.split("@")[1]

    domain_enrolled = enrolment.check_domain_status(domain)
    if domain_enrolled is not True:
        return google_chat.responses.DOMAIN_NOT_ENROLLED

    user_enrolled = enrolment.check_user_status(user)
    if user_enrolled is not True:
        return google_chat.responses.USER_NOT_ENROLLED

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
            background_tasks.add_task(
                caddy.handle_message,
                caddy_message=caddy_message,
                chat_client=google_chat,
            )
            return google_chat.responses.ACCEPTED
        case "CARD_CLICKED":
            match event["action"]["actionMethodName"]:
                case "Proceed":
                    caddy_message = google_chat.handle_proceed_query(event)
                    background_tasks.add_task(
                        caddy.handle_message,
                        caddy_message=caddy_message,
                        chat_client=google_chat,
                    )
                    return google_chat.responses.NO_CONTENT
                case "edit_query_dialog":
                    return google_chat.get_edit_query_dialog(event)
                case "receiveEditedQuery":
                    caddy_message = google_chat.handle_edited_query(event)
                    background_tasks.add_task(
                        caddy.handle_message,
                        caddy_message=caddy_message,
                        chat_client=google_chat,
                    )
                    return google_chat.responses.SUCCESS_DIALOG
                case "survey_response":
                    google_chat.handle_survey_response(event)
                    return google_chat.responses.ACCEPTED
                case "call_complete":
                    google_chat.finalise_caddy_call(event)
                    return google_chat.responses.ACCEPTED


@app.post("/google-chat/supervision")
async def google_chat_supervision_endpoint(
    event=Depends(verify_google_chat_supervision_request),
):
    """
    Handles inbound requests from Google Chat for Caddy Supervisor
    """
    google_chat = GoogleChat()
    user = event["user"]["email"]
    domain = user.split("@")[1]

    domain_enrolled = enrolment.check_domain_status(domain)
    if domain_enrolled is not True:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=google_chat.messages["domain_not_enrolled"],
        )

    user_enrolled = enrolment.check_user_status(user)
    if user_enrolled is not True:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=google_chat.messages["user_not_registered"],
        )

    match event["type"]:
        case "ADDED_TO_SPACE":
            match event["space"]["type"]:
                case "DM":
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content=google_chat.messages["introduce_caddy_supervisor_DM"],
                    )
                case "ROOM":
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content={
                            "text": google_chat.messages[
                                "introduce_caddy_supervisor_SPACE"
                            ].format(space=event["space"]["displayName"])
                        },
                    )
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
                    return Response(status_code=status.HTTP_204_NO_CONTENT)
                case "rejected_dialog":
                    reject_dialog = google_chat.get_supervisor_response(event)
                    return JSONResponse(
                        status_code=status.HTTP_200_OK, content=reject_dialog
                    )
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

                    return JSONResponse(
                        status_code=status.HTTP_200_OK, content=confirmation_of_receipt
                    )
                case "receiveDialog":
                    match event["message"]["annotations"][0]["slashCommand"][
                        "commandName"
                    ]:
                        case "/addUser":
                            return JSONResponse(content=google_chat.add_user(event))
                        case "/removeUser":
                            return JSONResponse(content=google_chat.remove_user(event))
        case "MESSAGE":
            match event["dialogEventType"]:
                case "REQUEST_DIALOG":
                    match event["message"]["annotations"][0]["slashCommand"][
                        "commandName"
                    ]:
                        case "/addUser":
                            return JSONResponse(
                                content=google_chat.get_user_details("Add")
                            )
                        case "/removeUser":
                            return JSONResponse(
                                content=google_chat.get_user_details("Remove")
                            )
                        case "/listUsers":
                            return JSONResponse(
                                content=google_chat.list_space_users(event)
                            )
                        case "/help":
                            return JSONResponse(content=google_chat.helper_dialog())


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
