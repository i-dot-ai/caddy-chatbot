from datetime import datetime
import boto3
import json
from models import ProcessChatMessageEvent, responses_table
from utils import idempotent, similar_question_dialog, edit_query_dialog
from responses import send_message_to_adviser_space, send_pii_warning_to_adviser_space
from anonymise import analyse, redact
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
patch_all()

serverless = boto3.client('lambda')

@xray_recorder.capture()
def handle_incoming_message(event):

    source_client = "Google Chat"
    message_string = event['message']['text']
    user = event['user']['email']
    space_id = event['space']['name'].split('/')[1]
    name = event['user']['name']
    timestamp = event['eventTime']
    thread_id = None
    if "thread" in event['message']:
        thread_id = event['message']['thread']['name'].split('/')[3]

    if "proceed" not in event:
        pii_identified = analyse(message_string)

        if pii_identified:
            message_string = redact(message_string, pii_identified)

            send_pii_warning_to_adviser_space(
            space_id=space_id,
            message="<b><font color=\"#FF0000\">PII DETECTED</font><b> <i>Please ensure all queries to Caddy are anonymised. \n\n Choose whether to proceed anyway or edit your original query<i>",
            thread_id=thread_id,
            message_event=event
            )

            return

    thread_id, message_id = send_message_to_adviser_space(
    space_id=space_id,
    message="*Status:* _*Processing*_",
    thread_id=thread_id
    )

    message_event = ProcessChatMessageEvent(
    type="PROCESS_CHAT_MESSAGE",
    user=user,
    name=name,
    space_id=space_id,
    thread_id=thread_id,
    message_id=message_id,
    message_string=message_string.replace('@Caddy', ''),
    source_client=source_client,
    timestamp=timestamp
    ).model_dump_json()

    serverless.invoke(
        FunctionName='llm',
        InvocationType='Event',
        Payload=message_event
    )

    return

@xray_recorder.capture()
def get_edit_query_dialog(event):
    message_string = event['message']['text']
    message_string = message_string.replace('@Caddy', '')

    return edit_query_dialog(event, message_string)

@xray_recorder.capture()
def get_similar_question_dialog(event):
    similar_question = event['common']['parameters']['llmPrompt']
    question_answer = event['common']['parameters']['llmAnswer']
    similarity = event['common']['parameters']['similarity']

    return similar_question_dialog(similar_question, question_answer, similarity)

@xray_recorder.capture()
def introduce_caddy(event):

    match event['space']['type']:
        case 'DM':
            return json.dumps({"text": "Hi, I'm Caddy! I'm an AI support for Citizens Advice advisers, I'm here to help give advice to support in resolving your client queries. \n *To get started just send me a query*"})
        case 'ROOM':
            return json.dumps({"text": f"Hi, thank you for adding me to {event['space']['displayName']}, I'm Caddy! I'm an AI support for Citizens Advice advisers, I'm here to help give advice to support in resolving your client queries. \n\n *Just remember to type `@Caddy` at the start of your query if you would like my help.*"})

@xray_recorder.capture()
def handle_survey_response(event):
    question = event['common']['parameters']['question']
    response = event['common']['parameters']['response']
    threadId = event['thread']['name'].split('/')[3]

    print(question, response, threadId)

    # TODO: implement survey response saving to DynamoDB
