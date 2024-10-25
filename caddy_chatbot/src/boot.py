# this is required from app, rather than the other way round,
# because currently requiring app has side effects we can't
# deal with yet
import os
import sys

from dotenv import load_dotenv

sys.path.append("caddy_chatbot/src")

if os.getenv("STAGE") == "dev":
    load_dotenv(".env")
elif os.getenv("STAGE") == "test":
    load_dotenv("test.env")
