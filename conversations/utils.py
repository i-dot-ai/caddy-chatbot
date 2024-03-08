from models import idempotent_table
from boto3.dynamodb.conditions import Key
import json

def similar_question_dialog(similar_question, question_answer, similarity):
  question_dialog = {
      "action_response": {
        "type": "DIALOG",
        "dialog_action": {
          "dialog": {
            "body": {
              "sections": [
                {
                  "header": f"<font color=\"#004f88\"><b>{similar_question}</b></font>",
                  "widgets": [
                    {
                      "textParagraph": {
                        "text": question_answer
                      }
                    },
                    {
                      "textParagraph": {
                        "text": f"<font color=\"#004f88\"><b>{similarity}% Match</b></font>"
                      }
                    }
                  ],
                }
              ]
            }
          }
        }
      }
    }
  return question_dialog

def edit_query_dialog(message_event, message_string):
    edit_query_dialog = {
      "action_response": {
        "type": "DIALOG",
        "dialog_action": {
          "dialog": {
            "body": {
              "sections": [
                {
                  "header": "PII Detected: Edit query",
                  "widgets": [
                    {
                      "textInput": {
                        "label": "Please edit your original query to remove PII",
                        "type": "MULTIPLE_LINE",
                        "name": "editedQuery",
                        "value": message_string
                      }
                    },
                    {
                      "buttonList": {
                        "buttons": [
                          {
                            "text": "Submit edited query",
                            "onClick": {
                              "action": {
                                "function": "receiveEditedQuery",
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
                        },
                      'horizontalAlignment': 'END'
                    }
                  ],
                }
              ]
            }
          }
        }
      }
    }
    return edit_query_dialog

def success_dialog():
    success_dialog = {
        "action_response": {
            "type": "DIALOG",
            "dialog_action": {
                "action_status": "OK"
            }
        }
    }
    return success_dialog

def idempotent():
    def decorator(func):
      def wrapper(event, *args, **kwargs):
          message_id = event['message']['name']

          response = idempotent_table.get_item(
              Key={
                  'id': str(message_id)
                }
            )

          if 'Item' in response:
              match response['Item']['status']:
                  case 'IN_PROGRESS':
                      return None
                  case 'FAILED':
                      return func(event, *args, **kwargs)
          else:
            idempotent_table.put_item(
              Item={
                  'id': str(message_id),
                  'status': 'IN_PROGRESS'
                  }
            )
            return func(event, *args, **kwargs)
      return wrapper
    return decorator
