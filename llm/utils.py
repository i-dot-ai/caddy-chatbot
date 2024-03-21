from models import responses_table, idempotent_table, offices_table
from boto3.dynamodb.conditions import Key
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
import json
from modules import module_registry
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

def get_user_workspace_variables(user_email : str):
  """ Takes a user table, and retrieves variables for user workspace """

  email_domain = user_email.split('@')[1]

  # find the relevant office in the table, and return their variable dictionary

  response = offices_table.get_item(
    Key={
      'emailDomain': email_domain
    }
  )

  # Convert the JSON string back to dictionary
  workspace_vars = json.loads(response['Item']['workspaceVars'])

  return workspace_vars


def execute_optional_modules(event, execution_time ):
  """ Executes optional modules linked to the user workspace"""

  suitable_time_strings = ['before_message_processed','after_message_processed','end_of_conversation']

  if execution_time not in suitable_time_strings:
    raise ValueError(f"Invalid execution time: {execution_time}. Must be one of {suitable_time_strings}")
  continue_conversation = True

  user_email = event['user']

  user_workspace_variables = get_user_workspace_variables(user_email)
  modules_to_use = user_workspace_variables[execution_time]

  module_outputs = {}
  for module in modules_to_use:
      module_name = module['module_name']
      module_arguments = module['module_arguments']

      try:
          module_func = module_registry[module_name]
      except KeyError:
          print(f"Module function '{module_name}' not found.")
          continue

      try:
          result = module_func(event=event, **module_arguments)
          module_outputs[module_name] = result

          if result[0] == 'end_interaction':
              continue_conversation = False
      except Exception as e:
          print(f"Error occurred while executing module '{module_name}': {str(e)}")

  # this will be received from API
  module_outputs_json = json.dumps(module_outputs)

  return modules_to_use, module_outputs_json, continue_conversation


def add_workspace_variables_to_table(email_domain : str, workspace_vars : dict):
  """Finds the relevant office in the office table and adds the workspace variables"""

  workspace_vars_json = json.dumps(workspace_vars)

  response = offices_table.update_item(
    Key={
      'emailDomain': email_domain
    },
    UpdateExpression="set workspaceVars=:w",
    ExpressionAttributeValues={
      ':w': workspace_vars_json
    },
    ReturnValues="UPDATED_NEW"
  )

  return response

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

# @xray_recorder.capture()
# def similar_question_dialog(similar_question, question_answer, similarity):
#   question_dialog = {
#       "action_response": {
#         "type": "DIALOG",
#         "dialog_action": {
#           "dialog": {
#             "body": {
#               "sections": [
#                 {
#                   "header": f"<font color=\"#004f88\"><b>{similar_question}</b></font>",
#                   "widgets": [
#                     {
#                       "textParagraph": {
#                         "text": question_answer
#                       }
#                     },
#                     {
#                       "textParagraph": {
#                         "text": f"<font color=\"#004f88\"><b>{similarity}% Match</b></font>"
#                       }
#                     }
#                   ],
#                 }
#               ]
#             }
#           }
#         }
#       }
#     }
#   return question_dialog

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
