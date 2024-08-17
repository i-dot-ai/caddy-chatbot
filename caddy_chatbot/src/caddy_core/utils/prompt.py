import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta

from caddy_core.utils.monitoring import logger
from caddy_core.services.router import get_route


def get_prompt(prompt_name):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(os.getenv("PROMPTS_TABLE_NAME"))

    response = table.get_item(Key={"PromptName": prompt_name})
    logger.info(f"Fetched prompt: {prompt_name}")
    return response["Item"]["Prompt"] if "Item" in response else None


def retrieve_route_specific_augmentation(query):
    refresh_session_token()
    route = get_route(query).name
    logger.info(f"Route returned: {route}")

    prompt_name = f"{route.upper()}_PROMPT"
    route_specific_augmentation = get_prompt(prompt_name)

    if route_specific_augmentation is None:
        logger.info("Route not found, using fallback prompt")
        route_specific_augmentation = get_prompt("FALLBACK_PROMPT")

    return route_specific_augmentation, route


def refresh_session_token():
    expiration_timestamp = os.environ.get("AWS_CREDENTIAL_EXPIRATION")
    if expiration_timestamp:
        expiration = datetime.fromisoformat(expiration_timestamp)
        if datetime.now(timezone.utc) < expiration - timedelta(minutes=5):
            logger.info("Credentials still valid, no refresh required")
            return

    try:
        sts_client = boto3.client("sts")
        temporary_credentials = sts_client.get_session_token(DurationSeconds=3600)

        credentials = temporary_credentials["Credentials"]

        os.environ["AWS_ACCESS_KEY_ID"] = credentials["AccessKeyId"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = credentials["SecretAccessKey"]
        os.environ["AWS_SESSION_TOKEN"] = credentials["SessionToken"]

        expiration_iso = credentials["Expiration"].astimezone(timezone.utc).isoformat()
        os.environ["AWS_CREDENTIAL_EXPIRATION"] = expiration_iso

        logger.info(
            f"Refreshed credentials, new expiry time: {os.environ['AWS_CREDENTIAL_EXPIRATION']}"
        )
    except ClientError as e:
        logger.error(f"Failed to refresh credentials: {e}")
        raise
