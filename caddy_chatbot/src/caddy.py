from fastapi import FastAPI, Depends, Request, status, BackgroundTasks
from fastapi.responses import JSONResponse, Response

import json
from caddy_core import core as caddy
from caddy_core.services import enrolment
from integrations.google_chat.core import GoogleChat
from integrations.local import core as caddy_local

from integrations.google_chat.verification import (
    verify_google_chat_request,
    verify_google_chat_supervision_request,
)

app = FastAPI(docs_url=None)

from threading import Thread


@app.get("/")
def root():
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN, content={"detail": "Forbidden"}
    )


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
        return JSONResponse(
            content=google_chat.messages["domain_not_enrolled"],
        )

    user_enrolled = enrolment.check_user_status(user)
    if user_enrolled is not True:
        return JSONResponse(
            content=google_chat.messages["user_not_registered"],
        )

    match event["type"]:
        case "ADDED_TO_SPACE":
            match event["space"]["type"]:
                case "DM":
                    return JSONResponse(
                        content=google_chat.messages["introduce_caddy_DM"]
                    )
                case "ROOM":
                    return JSONResponse(
                        content={
                            "text": google_chat.messages[
                                "introduce_caddy_SPACE"
                            ].format(space=event["space"]["displayName"])
                        }
                    )
        case "MESSAGE":
            caddy_message = google_chat.format_message(event)
            if caddy_message == "PII Detected":
                return Response(status_code=status.HTTP_204_NO_CONTENT)

            caddy.handle_message(caddy_message=caddy_message, chat_client=google_chat)

            return Response(status_code=status.HTTP_202_ACCEPTED)
        case "CARD_CLICKED":
            match event["action"]["actionMethodName"]:
                case "similarQuestionDialog":
                    similar_dialog = google_chat.get_similar_question_dialog(event)
                    return JSONResponse(
                        status_code=status.HTTP_200_OK, content=similar_dialog
                    )
                case "Proceed":
                    event = json.loads(event["common"]["parameters"]["message_event"])
                    event["proceed"] = True
                    caddy_message = google_chat.format_message(event)
                    background_tasks.add_task(
                        caddy.handle_message,
                        caddy_message=caddy_message,
                        chat_client=google_chat,
                    )
                    return Response(status_code=status.HTTP_204_NO_CONTENT)
                case "edit_query_dialog":
                    edit_query_dialog = google_chat.get_edit_query_dialog(event)
                    return JSONResponse(
                        status_code=status.HTTP_200_OK, content=edit_query_dialog
                    )
                case "receiveEditedQuery":
                    edited_message = event["common"]["formInputs"]["editedQuery"][
                        "stringInputs"
                    ]["value"][0]
                    event = json.loads(event["common"]["parameters"]["message_event"])
                    event["message"]["text"] = edited_message
                    caddy_message = google_chat.format_message(event)
                    background_tasks.add_task(
                        caddy.handle_message,
                        caddy_message=caddy_message,
                        chat_client=google_chat,
                    )
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content=google_chat.success_dialog(),
                    )
                case "survey_response":
                    background_tasks.add_task(
                        google_chat.handle_survey_response, event=event
                    )
                    return Response(status_code=status.HTTP_204_NO_CONTENT)
                case "call_complete":
                    survey_card = json.loads(event["common"]["parameters"]["survey"])
                    thread_id = event["message"]["thread"]["name"].split("/")[3]
                    user_space = event["space"]["name"].split("/")[1]
                    caddy.mark_call_complete(thread_id)
                    google_chat.run_survey(survey_card, user_space, thread_id)
                    google_chat.update_survey_card_in_adviser_space(
                        space_id=user_space,
                        message_id=event["message"]["name"].split("/")[3],
                        card={
                            "cardsV2": [
                                {
                                    "cardId": "callCompleteConfirmed",
                                    "card": {
                                        "sections": [
                                            {
                                                "widgets": [
                                                    {
                                                        "textParagraph": {
                                                            "text": '<font color="#00ba01"><b>📞 Call complete, please complete the post call survey below</b></font>'
                                                        }
                                                    },
                                                ],
                                            },
                                        ],
                                    },
                                },
                            ],
                        },
                    )
                    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        return JSONResponse(
            content=google_chat.messages["domain_not_enrolled"],
        )

    user_enrolled = enrolment.check_user_status(user)
    if user_enrolled is not True:
        return JSONResponse(
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
