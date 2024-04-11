import boto3
import botocore
import json

# --- RUN `sam local start-lambda` TO START THE LOCAL LAMBDA ENDPOINT ---
lambda_client = boto3.client(
    "lambda",
    region_name="eu-west-2",
    endpoint_url="http://127.0.0.1:3001",
    use_ssl=False,
    verify=False,
    config=botocore.client.Config(signature_version=botocore.UNSIGNED),
)


# --- RUN `pytest` TO RUN THE TESTS ---
def test_llm_invoke():
    with open("tests/events/ProcessChatMessageEvent.json") as event:
        PROCESS_CHAT_MESSAGE_EVENT = json.load(event)

    response = lambda_client.invoke(
        FunctionName="LlmFunction",
        InvocationType="RequestResponse",
        Payload=json.dumps(PROCESS_CHAT_MESSAGE_EVENT),
    )

    response = json.load(response["Payload"])

    assert response == "LLM Invoke Test"
