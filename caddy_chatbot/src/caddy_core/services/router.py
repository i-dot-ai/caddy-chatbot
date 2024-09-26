import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta

from semantic_router import Route, RouteLayer
from semantic_router.encoders import BedrockEncoder
from caddy_core.utils.monitoring import logger

from dotenv import load_dotenv

load_dotenv()


class AutoRefreshBedrockEncoder:
    def __init__(self, region="eu-west-3", score_threshold=0.5):
        self.region = region
        self.score_threshold = score_threshold
        self.encoder = None
        self.refresh_credentials()

    def refresh_credentials(self):
        try:
            sts_client = boto3.client("sts")
            role_arn = os.environ.get("TASK_ROLE_ARN")
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="CaddyTaskSession",
                DurationSeconds=3600,
            )

            credentials = response["Credentials"]
            self.encoder = BedrockEncoder(
                access_key_id=credentials["AccessKeyId"],
                secret_access_key=credentials["SecretAccessKey"],
                session_token=credentials["SessionToken"],
                region=self.region,
                score_threshold=self.score_threshold,
            )

            self.expiration = credentials["Expiration"]
            logger.info(f"Refreshed credentials, new expiry time: {self.expiration}")
        except ClientError as e:
            logger.error(f"Failed to refresh credentials: {e}")
            raise

    def __call__(self, *args, **kwargs):
        if datetime.now(timezone.utc) >= self.expiration - timedelta(minutes=5):
            logger.info("Credentials expiring soon, refreshing...")
            self.refresh_credentials()

        return self.encoder(*args, **kwargs)

    def __getattr__(self, name):
        if name == "score_threshold":
            return self.score_threshold
        return getattr(self.encoder, name)


embeddings = AutoRefreshBedrockEncoder(region="eu-west-3", score_threshold=0.5)

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
