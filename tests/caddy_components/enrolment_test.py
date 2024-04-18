import sys
from unittest.mock import patch, Mock

sys.path.append("/workspaces/caddy_chatbot/caddy_chatbot/src")
import boto3
from caddy_core.services import enrolment

# --- Create a local dynamo resource pointing to local instance --- #
dynamodb = boto3.client(
    "dynamodb",
    region_name="localhost",
    endpoint_url="http://localhost:8000",
    aws_access_key_id="dummy",
    aws_secret_access_key="dummy",  # pragma: allowlist secret
)

# --- Check and Create Cadd tables --- #

user_table = "caddy_test_users"
existing_tables = dynamodb.list_tables()["TableNames"]

if user_table not in existing_tables:
    mock_user_table = dynamodb.create_table(
        TableName=user_table,
        KeySchema=[{"AttributeName": "userEmail", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "userEmail", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
    )
    dynamodb.get_waiter("table_exists").wait(TableName=user_table)


### --- Enrolment Components --- ###
@patch("caddy_core.utils.tables.users_table")
def test_user_registration(mock_user_table):
    mock_user_table.return_value = Mock()

    # --- Test User Entry --- #
    user = "john.doe@caddy.test.org"
    role = "Adviser"
    supervisor_space_id = "12345"

    response = enrolment.register_user(user, role, supervisor_space_id)
    assert response["content"] == "user registration completed successfully"


@patch("caddy_core.utils.tables.users_table")
def test_list_users(mock_user_table):
    mock_user_table.return_value = Mock()

    # --- Test User Entry --- #
    users = [
        "john.doe@caddy.test.org",
        "jane.doe@caddy.test.org",
        "jane.smith@caddy.test.org",
        "john.smith@caddy.test.org",
    ]
    role = "Adviser"
    supervisor_space_id = "12345"

    for user in users:
        response = enrolment.register_user(user, role, supervisor_space_id)

    response = enrolment.list_users(supervision_space_id=supervisor_space_id)

    user_list = []

    for user in users:
        user_list.append(f"{user}: Adviser\n")

    assert response == "".join(user_list)


@patch("caddy_core.utils.tables.users_table")
def test_user_removal(mock_user_table):
    mock_user_table.return_value = Mock()

    # --- Test User Entry --- #
    user = "john.doe@caddy.test.org"

    response = enrolment.remove_user(user)
    assert response["content"] == "user deletion completed successfully"
