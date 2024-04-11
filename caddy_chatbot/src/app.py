from fastapi import FastAPI, Depends, Request, status, BackgroundTasks
from fastapi.responses import JSONResponse

from caddy_core import components as caddy
from caddy_core.services import enrolment
from caddy_core.models import UserMessage

from integrations.google_chat.structures import GoogleChat
from integrations.google_chat.verification import (
    verify_google_chat_request,
    verify_google_chat_supervision_request,
)


from threading import Thread

app = FastAPI(docs_url=None)


@app.get("/health")
def health():
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "Online"})


@app.post("/google-chat/chat")
def google_chat_endpoint(
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
                case "survey_response":
                    google_chat.handle_survey_response(event)
                    return google_chat.responses.ACCEPTED
                case "call_complete":
                    google_chat.finalise_caddy_call(event)
                    return google_chat.responses.ACCEPTED


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
                case "rejected_dialog":
                    reject_dialog = google_chat.get_supervisor_response(event)
                    return JSONResponse(
                        status_code=status.HTTP_200_OK, content=reject_dialog
                    )
                case "receiveSupervisorResponse":
                    google_chat.handle_supervisor_rejection(event)
                    return google_chat.responses.SUCCESS_DIALOG
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
async def caddy_endpoint(request: Request):
    query = await request.json()

    query = UserMessage.model_validate(query)

    caddy_query, caddy_documents = caddy.query_llm(message_query=query, chat_history=[])

    caddy_query = {"caddy_response": caddy_query.llm_answer}

    return JSONResponse(status_code=status.HTTP_200_OK, content=caddy_query)


@app.post("/caddy/supervision")
def caddy_supervision_endpoint(request: Request):
    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"text": "Request received"}
    )
