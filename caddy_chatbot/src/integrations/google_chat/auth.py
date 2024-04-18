import json
from google.oauth2 import service_account


def get_google_creds(google_service_account: dict):
    """
    Retrieves Google Chat credentials given a service account dict

    Args:
        service_account (dict): the service account info

    Returns:
        credentials: the constructed credentials.
    """
    scopes_list = ["https://www.googleapis.com/auth/chat.bot"]

    google_service_account = json.loads(google_service_account)

    credentials = service_account.Credentials.from_service_account_info(
        google_service_account, scopes=scopes_list
    )

    return credentials
