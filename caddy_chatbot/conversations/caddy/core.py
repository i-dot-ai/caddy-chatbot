from caddy.models.core import CaddyMessageEvent
from caddy.utils.tables import evaluation_table

import os
import boto3
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

serverless = boto3.client("lambda")


@xray_recorder.capture()
def handle_message(event: CaddyMessageEvent):
    serverless.invoke(
        FunctionName=f'llm-{os.getenv("STAGE")}',
        InvocationType="Event",
        Payload=event.model_dump_json(),
    )


def mark_call_complete(thread_id: str) -> None:
    """
    Mark the call as complete in the evaluation table

    Args:
        thread_id (str): The thread id of the conversation

    Returns:
        None
    """
    evaluation_table.update_item(
        Key={"threadId": thread_id},
        UpdateExpression="set callComplete = :cc",
        ExpressionAttributeValues={":cc": True},
    )
