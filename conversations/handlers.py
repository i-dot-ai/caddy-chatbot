from datetime import datetime
import boto3
import json
from models import ProcessChatMessageEvent, responses_table
from utils import idempotent, similar_question_dialog
from responses import send_message_to_adviser_space

serverless = boto3.client('lambda')

@idempotent()
def handle_incoming_message(event):

    try:
        message_string = event['message']['text']
        source_client = "Google Chat"
        user = event['user']['email']
        space_id = event['space']['name'].split('/')[1]
        name = event['user']['name']
        timestamp = event['eventTime']
        thread_id = None
        if "thread" in event['message']:
            thread_id = event['message']['thread']['name'].split('/')[3]
    except KeyError:
        message_string = event['message_string']
        source_client = "Unknown"
        user = "unknown@unknown.com"
        space_id = "Unknown"
        name = "Unknown"
        timestamp = "Unknown"

    thread_id, message_id = send_message_to_adviser_space(
        space_id=space_id,
        message="*Status:* _*Processing*_",
        thread_id=thread_id
        )

    message_string = message_string.replace('@Caddy', '')

    message_event = ProcessChatMessageEvent(
        type="PROCESS_CHAT_MESSAGE",
        user=user,
        name=name,
        space_id=space_id,
        thread_id=thread_id,
        message_id=message_id,
        message_string=message_string,
        source_client=source_client,
        timestamp=timestamp
    ).model_dump_json()

    serverless.invoke(
        FunctionName='llm',
        InvocationType='Event',
        Payload=message_event
    )

    return

def get_similar_question_dialog(event):
    similar_question = event['common']['parameters']['llmPrompt']
    question_answer = event['common']['parameters']['llmAnswer']
    similarity = event['common']['parameters']['similarity']

    return similar_question_dialog(similar_question, question_answer, similarity)

def introduce_caddy(event):

    match event['space']['type']:
        case 'DM':
            return json.dumps({"text": "Hi, I'm Caddy! I'm an AI support for Citizens Advice advisers, I'm here to help give advice to support in resolving your client queries. \n *To get started just send me a query*"})
        case 'ROOM':
            return json.dumps({"text": f"Hi, thank you for adding me to {event['space']['displayName']}, I'm Caddy! I'm an AI support for Citizens Advice advisers, I'm here to help give advice to support in resolving your client queries. \n\n *Just remember to type `@Caddy` at the start of your query if you would like my help.*"})
