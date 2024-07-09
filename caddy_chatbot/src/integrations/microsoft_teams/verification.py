from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import os

# Configure Bot
APP_ID = os.getenv("MicrosoftAppId", "")
APP_PASSWORD = os.getenv("MicrosoftAppPassword", "")

# Create adapter
SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
teams_adapter = BotFrameworkAdapter(SETTINGS)


class TeamsEndpointMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/microsoft-teams"):
            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
            response.headers["Access-Control-Allow-Headers"] = "*"
        else:
            response = await call_next(request)
        return response


async def on_turn(turn_context: TurnContext):
    if turn_context.activity.type == "message":
        await turn_context.send_activity(f"You said: {turn_context.activity.text}")
