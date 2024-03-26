from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()


class supervisor:
    pass


class caddy:
    pass


# Send message to the adviser space
@xray_recorder.capture()
def send_message_to_adviser_space(response_type, space_id, message, thread_id):
    match response_type:
        case "text":
            caddy.spaces().messages().create(
                parent=f"spaces/{space_id}",
                body={
                    "text": message,
                    "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
                },
                messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
            ).execute()
        case "cardsV2":
            caddy.spaces().messages().create(
                parent=f"spaces/{space_id}",
                body={
                    "cardsV2": message["cardsV2"],
                    "thread": {"name": f"spaces/{space_id}/threads/{thread_id}"},
                },
                messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
            ).execute()


# Update message in the supervisor space
@xray_recorder.capture()
def update_message_in_supervisor_space(
    space_id, message_id, new_message
):  # find message name
    supervisor.spaces().messages().patch(
        name=f"spaces/{space_id}/messages/{message_id}",
        updateMask="cardsV2",
        body=new_message,
    ).execute()


# Update message in the adviser space
@xray_recorder.capture()
def update_message_in_adviser_space(space_id, message_id, response_type, message):
    caddy.spaces().messages().patch(
        name=f"spaces/{space_id}/messages/{message_id}",
        updateMask=response_type,
        body=message,
    ).execute()


# Delete message in the adviser space
@xray_recorder.capture()
def delete_message_in_adviser_space(space_id, message_id):
    caddy.spaces().messages().delete(
        name=f"spaces/{space_id}/messages/{message_id}"
    ).execute()
