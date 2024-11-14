import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta

from semantic_router import Route, RouteLayer
from semantic_router.encoders import BedrockEncoder
from caddy_core.utils.monitoring import logger
from caddy_core.routes import routes_data

from semantic_router.index.postgres import PostgresIndex
from semantic_router.index.local import LocalIndex


from dotenv import load_dotenv

load_dotenv()


class CachedRouteLayer(RouteLayer):
    """
    Custom RouteLayer that skips initial encoding when using cached routes
    """

    def __init__(self, encoder, routes, index, **kwargs):
        super().__init__(encoder=encoder, index=index, **kwargs)
        self.routes = routes


class AutoRefreshBedrockEncoder:
    def __init__(self, region="eu-west-3", score_threshold=0.5):
        logger.info("Constructing encoder")
        self.region = region
        self.score_threshold = score_threshold
        self.encoder = None
        self.expiration = datetime.now(
            timezone.utc
        )  # assume we're expired when we construct

    def refresh_credentials(self):
        logger.info("Refreshing credentials")
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
        logger.info("Calling encoder")
        if datetime.now(timezone.utc) >= self.expiration - timedelta(minutes=5):
            logger.info("Credentials expiring soon, refreshing...")
            self.refresh_credentials()

        return self.encoder(*args, **kwargs)

    def __getattr__(self, name):
        if name == "score_threshold":
            return self.score_threshold
        return getattr(self.encoder, name)


def load_semantic_router() -> RouteLayer:
    routes = []
    for route in routes_data:
        utterances = route["utterances"]
        route = Route(name=route["name"], utterances=utterances)
        routes.append(route)

    if os.environ.get("POSTGRES_CONNECTION_STRING", False):
        logger.info(
            "POSTGRES_CONNECTION_STRING is set, looking for routes in postgres..."
        )
        index = PostgresIndex(dimensions=1024)
    else:
        index = LocalIndex()

    try:
        route_count_in_index = len(index.get_routes())
    except ValueError:
        route_count_in_index = 0

    if os.environ.get("TASK_ROLE_ARN", None):
        embeddings = AutoRefreshBedrockEncoder(region="eu-west-3", score_threshold=0.5)
    else:
        session = boto3.Session()
        credentials = session.get_credentials()
        embeddings = BedrockEncoder(
            region="eu-west-3",
            score_threshold=0.5,
            access_key_id=credentials.access_key,
            secret_access_key=credentials.secret_key,
        )

    if route_count_in_index > 0:
        logger.info(f"Loading {route_count_in_index} routes from index...")
        return CachedRouteLayer(encoder=embeddings, routes=routes, index=index)
    else:
        return RouteLayer(encoder=embeddings, routes=routes, index=index)


get_route = load_semantic_router()
