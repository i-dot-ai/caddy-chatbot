import pytest
import caddy_chatbot.src.boot  # noqa: F401

from utils.setup_dynamo import setup_dynamo
from caddy_core.utils.monitoring import logger


@pytest.fixture(autouse=True, scope="session")
def setup_test_dynamo():
    logger.info("Setting up test dynamoDB")
    setup_dynamo(logger)
