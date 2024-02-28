from events import receive_new_ai_response, received_approval, received_rejection, get_user_details, add_user, remove_user, list_users, get_supervisor_response, introduce_caddy_supervisor
from utils import helper_dialog

def lambda_handler(event, context):

    print(f'### EVENT RECEIVED \n\n {event} \n\n ### END OF EVENT')

    match event['type']:
        case 'SUPERVISION_REQUIRED':
            receive_new_ai_response(event)
        case 'CARD_CLICKED':
            match event['action']['actionMethodName']:
                case 'Approved':
                    received_approval(event)
                case 'rejected_dialog':
                    return get_supervisor_response(event)
                case 'receiveSupervisorResponse':
                    received_rejection(event)
                case 'receiveDialog':
                    match event['message']['annotations'][0]['slashCommand']['commandName']:
                        case '/addUser':
                            return add_user(event)
                        case '/removeUser':
                            return remove_user(event)
        case 'MESSAGE':
            match event['dialogEventType']:
                case 'REQUEST_DIALOG':
                    match event['message']['annotations'][0]['slashCommand']['commandName']:
                        case '/addUser':
                            return get_user_details('Add')
                        case '/removeUser':
                            return get_user_details('Remove')
                        case '/listUsers':
                            return list_users(event)
                        case '/help':
                            return helper_dialog()
        case 'ADDED_TO_SPACE':
            return introduce_caddy_supervisor(event)
        case other:
            print("Case not handled")
