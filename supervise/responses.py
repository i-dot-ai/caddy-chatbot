import boto3
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

def get_google_creds(recepient: str):
  secret_manager = boto3.client('secretsmanager')
  scopes_list = [
      'https://www.googleapis.com/auth/chat.bot'
  ]
  credentials_dict = secret_manager.get_secret_value(SecretId=recepient)
  credentials_json = json.loads(credentials_dict['SecretString'])
  credentials = service_account.Credentials.from_service_account_info(credentials_json, scopes=scopes_list)

  return credentials

# Build the Chat API clients
supervisor = build('chat', 'v1', credentials=get_google_creds('GCPCred'))
caddy = build('chat', 'v1', credentials=get_google_creds('CaddyCred'))

# Send message to the supervisor space
def send_message_to_supervisor_space(space_id, message):
    response = supervisor.spaces().messages().create(
        parent=f"spaces/{space_id}",
        body=message
    ).execute()

    thread_id = response['thread']['name'].split('/')[3]
    message_id = response['name'].split('/')[3]

    return thread_id, message_id

def respond_to_supervisor_thread(space_id, message, thread_id):
    supervisor.spaces().messages().create(
        parent=f"spaces/{space_id}",
        body={
           "cardsV2": message['cardsV2'],
           "thread": {
              "name": f"spaces/{space_id}/threads/{thread_id}"
           }
        },
        messageReplyOption='REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD'
    ).execute()

# Send message to the adviser space
def send_message_to_adviser_space(response_type, space_id, message, thread_id):
    match response_type:
        case 'text':
            caddy.spaces().messages().create(
                parent=f"spaces/{space_id}",
                body={
                "text": message,
                "thread": {
                    "name": f"spaces/{space_id}/threads/{thread_id}"
                }
                },
                messageReplyOption='REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD'
            ).execute()
        case 'cardsV2':
            caddy.spaces().messages().create(
                parent=f"spaces/{space_id}",
                body={
                "cardsV2": message['cardsV2'],
                "thread": {
                    "name": f"spaces/{space_id}/threads/{thread_id}"
                }
                },
                messageReplyOption='REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD'
            ).execute()

# Update message in the supervisor space
def update_message_in_supervisor_space(space_id, message_id, new_message):  # find message name
    supervisor.spaces().messages().patch(
        name=f"spaces/{space_id}/messages/{message_id}",
        updateMask="cardsV2",
        body=new_message,
    ).execute()

# Update message in the adviser space
def update_message_in_adviser_space(space_id, message_id, response_type, message):
    caddy.spaces().messages().patch(
        name=f"spaces/{space_id}/messages/{message_id}",
        updateMask=response_type,
        body=message
    ).execute()

# Delete message in the adviser space
def delete_message_in_adviser_space(space_id, message_id):
    caddy.spaces().messages().delete(
        name=f"spaces/{space_id}/messages/{message_id}"
    ).execute()
