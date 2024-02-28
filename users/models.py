import pydantic
from datetime import datetime
from pydantic.types import StrictBool
import boto3
import os


# === Data Models ===
class User(pydantic.BaseModel):
    user_email: str
    is_approver: StrictBool = False
    is_super_user: StrictBool = False
    created_at: datetime = datetime.now()
    supervision_space_id: str


# === Database functions ===
def create_db_users_table(connection):
    """Creates the user table in the database"""

    table = connection.create_table(
        TableName='caddyUsers',
        KeySchema=[
            {'AttributeName': 'userEmail', 'KeyType': 'HASH'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'userEmail', 'AttributeType': 'S'},
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        }
    )


# === Database Connections ===
dynamodb = boto3.resource('dynamodb')

try:
    create_db_users_table(dynamodb)
except:
    print('user table already exists')

users_table = dynamodb.Table(os.getenv('USERS_TABLE_NAME'))
