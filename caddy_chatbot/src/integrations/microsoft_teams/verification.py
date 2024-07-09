from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity, ActivityTypes

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
        try:
            # Log incoming activity for debugging
            print(f"Received activity: {turn_context.activity.as_dict()}")
            
            if not turn_context.activity.service_url:
                print("service_url is missing from the activity")
                return

            # Create a response activity
            response = Activity(
                type=ActivityTypes.message,
                text=f"You said: {turn_context.activity.text}",
                service_url=turn_context.activity.service_url,
                channel_id=turn_context.activity.channel_id,
                conversation=turn_context.activity.conversation,
                recipient=turn_context.activity.from_property,
                from_property=turn_context.activity.recipient
            )

            # Send the response
            await turn_context.send_activity(response)
        except Exception as e:
            print(f"Error in on_turn: {str(e)}")