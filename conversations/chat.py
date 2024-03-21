from handlers import handle_incoming_message, get_similar_question_dialog, introduce_caddy, get_edit_query_dialog, handle_survey_response
from utils import success_dialog
from models import offices_table, users_table
import json

def lambda_handler(event, context):

    user = event['user']['email']
    domain = user.split('@')[1]

    if domain == 'gmail.com':
        return json.dumps({"text": "Caddy is not currently available for personal use."})

    user_registered = users_table.get_item(Key={"userEmail": user})
    office_registered = offices_table.get_item(Key={"emailDomain": domain})

    if "Item" in office_registered:
        if "Item" in user_registered:
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
                        case 'survey_response':
                            handle_survey_response(event)
                case 'MESSAGE':
                    return handle_incoming_message(event)
                case 'ADDED_TO_SPACE':
                    return introduce_caddy(event)
        else:
            return json.dumps({"text": "User is not registered, please contact it.support@casort.org for support in onboarding to Caddy"})
    else:
        return json.dumps({"text": "Office is not registered, please contact it.support@casort.org regarding onboarding to Caddy"})
