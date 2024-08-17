import os
import boto3
from semantic_router import Route, RouteLayer
from semantic_router.encoders import BedrockEncoder
from caddy_core.utils.monitoring import logger

session = boto3.Session()
credentials = session.get_credentials()
embeddings = BedrockEncoder(
    access_key_id=credentials.access_key,
    secret_access_key=credentials.secret_key,
    session_token=credentials.token,
    region="eu-west-3",
)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv("ROUTES_TABLE_NAME"))


def get_routes_dynamically():
    logger.info("Fetching routes")
    response = table.scan()
    routes = []
    for item in response["Items"]:
        utterances = item["utterances"]
        if isinstance(utterances[0], list):
            utterances = utterances[0]
        route = Route(name=item["name"], utterances=utterances)
        routes.append(route)
    logger.info(f"Fetched {len(routes)} routes")
    return routes


routes = get_routes_dynamically()

get_route = RouteLayer(encoder=embeddings, routes=routes)
