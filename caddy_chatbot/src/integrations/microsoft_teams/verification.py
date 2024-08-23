import os
import requests

APP_ID = os.environ.get("MicrosoftAppId", "")
APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")

url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
headers = {
    "Host": "login.microsoftonline.com",
    "Content-Type": "application/x-www-form-urlencoded",
}

authentication_data = {
    "grant_type": "client_credentials",
    "client_id": APP_ID,
    "client_secret": APP_PASSWORD,
    "scope": "https://api.botframework.com/.default",
}


def get_access_token():
    """
    Fetches an access token using the Bot credentials
    """
    response = requests.post(url, headers=headers, data=authentication_data)

    if response.status_code == 200:
        response_data = response.json()
        access_token = response_data.get("access_token")
        return access_token
    else:
        print("Failed to retrieve token:", response.text)
