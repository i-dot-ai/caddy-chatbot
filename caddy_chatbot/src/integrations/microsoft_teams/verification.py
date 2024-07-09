from botbuilder.core import (
    BotFrameworkAdapter,
    ActivityHandler,
    TurnContext,
    MessageFactory
)
from botbuilder.schema import ChannelAccount

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import os


class DefaultConfig:
    """ Bot Configuration """

    PORT = 3978
    APP_ID = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
    APP_TYPE = os.environ.get("MicrosoftAppType", "MultiTenant")
    APP_TENANTID = os.environ.get("MicrosoftAppTenantId", "")


teams_adapter = BotFrameworkAdapter(DefaultConfig)


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


class TeamsBot(ActivityHandler):
    async def on_members_added_activity(
        self, members_added: [ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Hello and welcome!")

    async def on_message_activity(self, turn_context: TurnContext):
        return await turn_context.send_activity(
            MessageFactory.text(f"Echo: {turn_context.activity.text}")
        )
    
TEAMS_BOT = TeamsBot()