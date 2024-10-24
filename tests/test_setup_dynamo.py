import pytest
from utils.setup_dynamo import setup_dynamo
from caddy_core.utils.monitoring import logger


def test_setup_dynamo(monkeypatch):
    monkeypatch.setenv("STAGE", "not-dev")

    with pytest.raises(Exception, match="non-dev environment"):
        setup_dynamo(logger)
