from handlers import process_chat_message


def lambda_handler(event, context):
    match event["type"]:
        case "PROCESS_CHAT_MESSAGE":
            process_chat_message(event)
