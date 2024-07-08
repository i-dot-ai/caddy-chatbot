from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
import asyncio


import os

# Configure Bot
APP_ID = os.getenv("MicrosoftAppId", "")
APP_PASSWORD = os.getenv("MicrosoftAppPassword", "")

# Create adapter
SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
teams_adapter = BotFrameworkAdapter(SETTINGS)


def on_turn(turn_context: TurnContext):
    if turn_context.activity.type == "message":
        # Use run_sync to run the asynchronous send_activity method
        asyncio.run_sync(
            turn_context.send_activity(f"You said: {turn_context.activity.text}")
        )
