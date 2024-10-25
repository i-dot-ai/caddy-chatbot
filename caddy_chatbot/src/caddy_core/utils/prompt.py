from caddy_core.utils.monitoring import logger
from caddy_core.services.router import get_route
from caddy_core.utils.tables import prompts_table as table
from caddy_core.utils import prompts


def get_local_prompt(prompt_name: str):
    logger.info(f"Fetching {prompt_name} from local prompts")

    PROMPT_MAP = {name: getattr(prompts, name) for name in prompts.__all__}

    prompt = PROMPT_MAP.get(prompt_name.split("_PROMPT")[0], None)

    if prompt is None:
        logger.warning("Prompt not found locally, using fallback prompt")
        prompt = PROMPT_MAP["FALLBACK"]

    return prompt


def get_prompt(prompt_name):
    logger.info(f"Attempting to fetch {prompt_name} from dynamodb")
    response = table.get_item(Key={"PromptName": prompt_name})
    if "Item" in response:
        prompt = response["Item"]["Prompt"]
    else:
        logger.warning("No prompt found in dynamodb")
        prompt = get_local_prompt(prompt_name)
    logger.info(f"Fetched prompt: {prompt_name}")
    return prompt


def retrieve_route_specific_augmentation(query):
    route = get_route(query).name
    logger.info(f"Route returned: {route}")

    if route:
        prompt_name = f"{route.upper()}_PROMPT"
        route_specific_augmentation = get_prompt(prompt_name)

    if route is None:
        logger.info("Route not found, using fallback prompt")
        route_specific_augmentation = get_prompt("FALLBACK_PROMPT")

    return route_specific_augmentation, route
