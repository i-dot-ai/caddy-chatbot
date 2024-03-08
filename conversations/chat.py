from handlers import handle_incoming_message, get_similar_question_dialog, introduce_caddy, get_edit_query_dialog
from utils import success_dialog
import json

def lambda_handler(event, context):

    match event['type']:
        case 'CARD_CLICKED':
            match event['action']['actionMethodName']:
                case 'similarQuestionDialog':
                    return get_similar_question_dialog(event)
                case 'Proceed':
                    event = json.loads(event['common']['parameters']['message_event'])
                    event['proceed'] = True
                    return handle_incoming_message(event)
                case 'edit_query_dialog':
                    event = json.loads(event['common']['parameters']['message_event'])
                    return get_edit_query_dialog(event)
                case 'receiveEditedQuery':
                    edited_message = event['common']['formInputs']['editedQuery']['stringInputs']['value'][0]
                    event = json.loads(event['common']['parameters']['message_event'])
                    event['message']['text'] = edited_message
                    handle_incoming_message(event)
                    return success_dialog()
        case 'MESSAGE':
            return handle_incoming_message(event)
        case 'ADDED_TO_SPACE':
            return introduce_caddy(event)
