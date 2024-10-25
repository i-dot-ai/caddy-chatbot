from setup_dynamo import sync_prompts
from caddy_core.utils.monitoring import logger

if __name__ == "__main__":
    sync_prompts(logger)
