from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
)

import os

# Configure Bot
APP_ID = os.getenv("MicrosoftAppId", "")
APP_PASSWORD = os.getenv("MicrosoftAppPassword", "")

# Create adapter
SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
teams_adapter = BotFrameworkAdapter(SETTINGS)
