import boto3
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

@xray_recorder.capture()
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
caddy = build('chat', 'v1', credentials=get_google_creds('CaddyCred'))

# Send message to the adviser space
@xray_recorder.capture()
def send_message_to_adviser_space(space_id: str, message, thread_id):
    response = caddy.spaces().messages().create(
        parent=f"spaces/{space_id}",
        body={
           "text": message,
           "thread": {
              "name": f"spaces/{space_id}/threads/{thread_id}"
           }
        },
        messageReplyOption='REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD'
    ).execute()

    thread_id = response['thread']['name'].split('/')[3]
    message_id = response['name'].split('/')[3]

    return thread_id, message_id

# Update message in the adviser space
@xray_recorder.capture()
def update_message_in_adviser_space(space_id: str, message_id: str, message):
    caddy.spaces().messages().patch(
        name=f"spaces/{space_id}/messages/{message_id}",
        body=message,
        updateMask='text'
    ).execute()

@xray_recorder.capture()
def update_survey_card_in_adviser_space(space_id: str, message_id: str, card):
    caddy.spaces().messages().patch(
        name=f"spaces/{space_id}/messages/{message_id}",
        body=card,
        updateMask='cardsV2'
    ).execute()

# Send message to the adviser space
@xray_recorder.capture()
def send_pii_warning_to_adviser_space(space_id: str, message, thread_id, message_event):
    caddy.spaces().messages().create(
        parent=f"spaces/{space_id}",
        body={
           "cardsV2": [
          {
            "cardId": "PIIDetected",
            "card": {
              "sections": [
                    {
                "widgets": [
                    {
                    "textParagraph": {
                        "text": message
                        }
                    },
                ],
                },{
                "widgets": [
                  {
                    "buttonList": {
                    "buttons": [
                    {
                        "text": "Proceed without redaction",
                        "onClick": {
                            "action": {
                            "function": "Proceed",
                            "parameters": [
                                {
                                "key": 'message_event',
                                "value": json.dumps(message_event)
                                },
                            ]
                            }
                        }
                    }, {
                        "text": "Edit original query",
                        "onClick": {
                            "action": {
                            "function": "edit_query_dialog",
                            "interaction": "OPEN_DIALOG",
                            "parameters": [
                                {
                                "key": 'message_event',
                                "value": json.dumps(message_event)
                                },
                              ]
                            }
                          }
                        }
                      ]
                    }
                    }
                  ],
                }
              ],
            },
          },
        ],
        "thread": {
            "name": f"spaces/{space_id}/threads/{thread_id}"
        }
        },
        messageReplyOption='REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD'
    ).execute()
