import caddy_chatbot.src.boot  # noqa: F401

import logging
from utils.setup_dynamo import setup_dynamo

# Logging
logger = logging.getLogger("caddy_tests")
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler("logs/test.log")

handler.setLevel(logging.INFO)
handler.setFormatter(formatter)

logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Setup dynamodb
setup_dynamo(logger)
