import boto3
import json
from google.oauth2 import service_account

def get_google_creds(recepient: str):
  """
  Retrieves Google Chat credentials from AWS Secrets Manager
  """
  secret_manager = boto3.client('secretsmanager')

  scopes_list = [
      'https://www.googleapis.com/auth/chat.bot'
  ]

  credentials_dict = secret_manager.get_secret_value(SecretId=recepient)
  credentials_json = json.loads(credentials_dict['SecretString'])
  credentials = service_account.Credentials.from_service_account_info(credentials_json, scopes=scopes_list)

  return credentials
