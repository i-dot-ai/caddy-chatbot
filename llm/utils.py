from models import responses_table, idempotent_table
from boto3.dynamodb.conditions import Key
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
patch_all()

@xray_recorder.capture()
def get_chat_history(message):
    # retrieve list of messages with same conversation_id from message database
    # change to get thread messages from API
    response = responses_table.query(
        KeyConditionExpression=Key("threadId").eq(message.thread_id),
    )
    history = format_chat_history(response['Items'])
    return history

@xray_recorder.capture()
def format_chat_history(user_messages):
    """ Formats chat messages for LangChain """
    history_langchain_format = []
    for message in user_messages:
        human = message["llmPrompt"]
        ai = message["llmAnswer"]
        history_langchain_format.append((human, ai))
    return history_langchain_format

@xray_recorder.capture()
def create_card(ai_response):
    card = {
        "cardsV2": [
          {
            "cardId": "aiResponseCard",
            "card": {
              "sections": [
              ],
            },
          },
        ],
      }

    ai_response_section = {
              "widgets": [
                {
                  "textParagraph": {
                    "text": ai_response['result']
                      }
                 },
              ],
            }

    card['cardsV2'][0]['card']['sections'].append(ai_response_section)

    reference_links_section = {
                "header": "Reference links",
                    "widgets": [
                  ]
                }

    for document in ai_response['source_documents']:
        reference_link = {
                      "textParagraph": {
                        "text": f"<a href=\"{document.metadata['source_url']}\">{document.metadata['source_url']}</a>"
                      }
                    }
        if reference_link not in reference_links_section['widgets']:
            reference_links_section['widgets'].append(reference_link)

    card['cardsV2'][0]['card']['sections'].append(reference_links_section)

    return card

@xray_recorder.capture()
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

@xray_recorder.capture()
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


# For clearer printing
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
