import os
import boto3

from caddy_core.utils.monitoring import logger
from caddy_core.services.router import get_route


def get_prompt(prompt_name):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(os.getenv("PROMPTS_TABLE_NAME"))

    response = table.get_item(Key={"PromptName": prompt_name})
    logger.info(f"Fetched prompt: {prompt_name}")
    return response["Item"]["Prompt"] if "Item" in response else None


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
