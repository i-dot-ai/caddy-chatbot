from fastapi import FastAPI, Depends, Request, status
from fastapi.responses import JSONResponse, Response

from caddy_core.utils.monitoring import logger
from caddy_core.models import UserNotEnrolledException, NoSupervisionSpaceException

from integrations.google_chat.structures import GoogleChat
from integrations.google_chat.verification import (
    verify_google_chat_request,
    verify_google_chat_supervision_request,
)


from integrations.microsoft_teams.structures import MicrosoftTeams

app = FastAPI(docs_url=None)

google_chat = GoogleChat()


@app.get("/health")
def health():
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "Online"})


@app.post("/google-chat/chat")
async def google_chat_endpoint(event=Depends(verify_google_chat_request)) -> dict:
    """
    Handles inbound requests from Google Chat for Caddy
    """
    logger.debug("New Google Chat Request")
    try:
        return await google_chat.handle_event(event)
    except UserNotEnrolledException:
        return google_chat.responses.USER_NOT_ENROLLED
    except NoSupervisionSpaceException:
        return google_chat.responses.NO_SUPERVISION_SPACE
    except Exception as e:
        logger.error(f"Error processing Google Chat request: {str(e)}")
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.post("/google-chat/supervision")
async def google_chat_supervision_endpoint(
    event=Depends(verify_google_chat_supervision_request),
):
    """
    Handles inbound requests from Google Chat for Caddy Supervisor
    """
    logger.info("New Google Chat Supervision Request")
    google_chat = GoogleChat()
    try:
        return await google_chat.handle_supervision_event(event)
    except UserNotEnrolledException:
        return google_chat.responses.USER_NOT_SUPERVISOR
    except Exception as e:
        logger.error(f"Error processing Google Chat supervision request: {str(e)}")
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.post("/microsoft-teams/chat")
async def microsoft_teams_endpoint(request: Request):
    event = await request.json()
    logger.debug(f"POST request received: {event}")

    try:
        microsoft_teams = MicrosoftTeams(event)
        return await microsoft_teams.handle_event(event)
    except UserNotEnrolledException:
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    except NoSupervisionSpaceException:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error processing Microsoft Teams supervision request: {str(e)}")
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.post("/microsoft-teams/supervision")
async def microsoft_teams_supervision_endpoint(request: Request):
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
