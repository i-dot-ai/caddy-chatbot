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
def test_enrolment_domain_true():
    with open("tests/events/CaddyLocalMessageEvent.json") as event:
        CONVERSATIONS_EVENT = json.load(event)

    response = lambda_client.invoke(
        FunctionName="ConversationsFunction",
        InvocationType="RequestResponse",
        Payload=json.dumps(CONVERSATIONS_EVENT),
    )

    response = json.load(response["Payload"])
    response = json.loads(response)

    with open("tests/events/ProcessChatMessageEvent.json") as result:
        PROCESS_CHAT_MESSAGE = json.load(result)

    assert response == PROCESS_CHAT_MESSAGE


def test_enrolment_domain_false():
    with open("tests/events/CaddyLocalMessageEvent_UnknownDomain.json") as event:
        CONVERSATIONS_EVENT = json.load(event)

    response = lambda_client.invoke(
        FunctionName="ConversationsFunction",
        InvocationType="RequestResponse",
        Payload=json.dumps(CONVERSATIONS_EVENT),
    )

    response = json.load(response["Payload"])
    response = json.loads(response)

    assert response == {
        "text": "Your domain is not enrolled in Caddy. Please contact your administrator."
    }


def test_enrolment_user_true():
    with open("tests/events/CaddyLocalMessageEvent.json") as event:
        CONVERSATIONS_EVENT = json.load(event)

    response = lambda_client.invoke(
        FunctionName="ConversationsFunction",
        InvocationType="RequestResponse",
        Payload=json.dumps(CONVERSATIONS_EVENT),
    )

    response = json.load(response["Payload"])
    response = json.loads(response)

    with open("tests/events/ProcessChatMessageEvent.json") as result:
        PROCESS_CHAT_MESSAGE = json.load(result)

    assert response == PROCESS_CHAT_MESSAGE


def test_enrolment_user_false():
    with open("tests/events/CaddyLocalMessageEvent_UnknownUser.json") as event:
        CONVERSATIONS_EVENT = json.load(event)

    response = lambda_client.invoke(
        FunctionName="ConversationsFunction",
        InvocationType="RequestResponse",
        Payload=json.dumps(CONVERSATIONS_EVENT),
    )

    response = json.load(response["Payload"])
    response = json.loads(response)

    assert response == {
        "text": "User is not registered, please contact your administrator for support in onboarding to Caddy"
    }


def test_conversations_invoke():
    with open("tests/events/CaddyLocalMessageEvent.json") as event:
        CONVERSATIONS_EVENT = json.load(event)

    response = lambda_client.invoke(
        FunctionName="ConversationsFunction",
        InvocationType="RequestResponse",
        Payload=json.dumps(CONVERSATIONS_EVENT),
    )

    response = json.load(response["Payload"])
    response = json.loads(response)

    with open("tests/events/ProcessChatMessageEvent.json") as result:
        PROCESS_CHAT_MESSAGE = json.load(result)

    assert response == PROCESS_CHAT_MESSAGE


def test_pii_detection():
    with open("tests/events/CaddyLocalMessageEvent_PII.json") as event:
        PII_EVENT = json.load(event)

    response = lambda_client.invoke(
        FunctionName="ConversationsFunction",
        InvocationType="RequestResponse",
        Payload=json.dumps(PII_EVENT),
    )

    response = response["Payload"].read().decode()

    assert response.strip('"') == "PII_DETECTED"
