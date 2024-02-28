from handlers import handle_incoming_message, get_similar_question_dialog, introduce_caddy

def lambda_handler(event, context):

    match event['type']:
        case 'CARD_CLICKED':
            match event['action']['actionMethodName']:
                case 'similarQuestionDialog':
                    return get_similar_question_dialog(event)
        case 'MESSAGE':
            return handle_incoming_message(event)
        case 'ADDED_TO_SPACE':
            return introduce_caddy(event)
