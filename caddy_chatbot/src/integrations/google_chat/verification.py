import os
from oauth2client import client
from fastapi import HTTPException, status, Request

CHAT_ISSUER = "chat@system.gserviceaccount.com"
PUBLIC_CERT_URL_PREFIX = "https://www.googleapis.com/service_accounts/v1/metadata/x509/"


async def verify_google_chat_request(request: Request) -> Request:
    """
    This function verifies the incoming request from Google Chat.

    Returns:
        Request: if verified as a request from Google Chat
        401: if request could not be verified
    """

    bearer_token = request.headers["Authorization"].split(" ")[1]
    audience = os.environ.get("CADDY_GOOGLE_CLOUD_PROJECT")

    try:
        token = client.verify_id_token(
            bearer_token, audience, cert_uri=PUBLIC_CERT_URL_PREFIX + CHAT_ISSUER
        )

        if token["iss"] != CHAT_ISSUER:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
            )
    except Exception as error:
        print(f"Error: {error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    event = await request.json()

    return event


async def verify_google_chat_supervision_request(request: Request) -> Request:
    """
    This function verifies the incoming google chat request from Caddy Supervisor.

    Args:
        request (Request): the incoming request

    Returns:
        Request: if verified as a request from Google Chat
        401: if request could not be verified
    """

    bearer_token = request.headers["Authorization"].split(" ")[1]
    audience = os.environ["CADDY_SUPERVISOR_GOOGLE_CLOUD_PROJECT"]

    try:
        token = client.verify_id_token(
            bearer_token, audience, cert_uri=PUBLIC_CERT_URL_PREFIX + CHAT_ISSUER
        )

        if token["iss"] != CHAT_ISSUER:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
            )
    except Exception as error:
        print(f"Error: {error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    event = await request.json()

    return event
