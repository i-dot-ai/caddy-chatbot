import json
from caddy import core as caddy
from caddy.services import enrolment
from integrations.google_chat.core import GoogleChat

def lambda_handler(event, context):

    chat_client = ''

    if 'common' in event and event['common']['hostApp'] == 'CHAT':
        chat_client = 'Google Chat'
    elif 'channelId' in event and event['channelId'] == 'msteams':
        chat_client = 'Microsoft Teams'
    elif 'type' in event and event['type'] == 'ADDED_TO_SPACE':
        chat_client = 'Google Chat'

    match chat_client:
        case 'Google Chat':
            """
            Handles inbound requests from Google Chat
            """
            google_chat = GoogleChat()
            user = event['user']['email']
            domain = user.split('@')[1]
            domain_enrolled = enrolment.check_domain_status(domain)
            match domain_enrolled:
                case True:
                    user_enrolled = enrolment.check_user_status(user)
                    match user_enrolled:
                        case True:
                            match event['type']:
                                case 'ADDED_TO_SPACE':
                                    match event['space']['type']:
                                        case 'DM':
                                            return google_chat.messages['introduce_caddy_DM']
                                        case 'ROOM':
                                            return json.dumps({"text": google_chat.messages['introduce_caddy_SPACE'].format(space=event['space']['displayName']) })
                                case 'MESSAGE':
                                    caddy_message = google_chat.format_message(event)
                                    if caddy_message == "PII Detected":
                                        return
                                    return caddy.handle_message(caddy_message)
                                case 'CARD_CLICKED':
                                    match event['action']['actionMethodName']:
                                        case 'similarQuestionDialog':
                                            return google_chat.get_similar_question_dialog(event)
                                        case 'Proceed':
                                            event = json.loads(event['common']['parameters']['message_event'])
                                            event['proceed'] = True
                                            caddy_message = google_chat.format_message(event)
                                            return caddy.handle_message(caddy_message)
                                        case 'edit_query_dialog':
                                            return google_chat.get_edit_query_dialog(event)
                                        case 'receiveEditedQuery':
                                            edited_message = event['common']['formInputs']['editedQuery']['stringInputs']['value'][0]
                                            event = json.loads(event['common']['parameters']['message_event'])
                                            event['message']['text'] = edited_message
                                            caddy_message = google_chat.format_message(event)
                                            caddy.handle_message(caddy_message)
                                            return google_chat.success_dialog()
                                        case 'survey_response':
                                            google_chat.handle_survey_response(event)
                        case False:
                            return google_chat.messages['user_not_registered']
                case False:
                    return google_chat.messages['domain_not_enrolled']
        case 'Microsoft Teams':
            """
            TODO - Add Microsoft Teams support
            """
            return json.dumps({"text": "Caddy is not currently available for this platform."})
        case other:
            return json.dumps({"text": "Caddy is not currently available for this platform."})
