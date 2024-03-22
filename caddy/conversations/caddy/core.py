import boto3
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
patch_all()

serverless = boto3.client('lambda')

@xray_recorder.capture()
def handle_message(CaddyMessageEvent):
    serverless.invoke(
        FunctionName='llm',
        InvocationType='Event',
        Payload=CaddyMessageEvent.model_dump_json()
    )
