import json

from models import User, users_table


def store_user(user: User):
    # Storing in DynamoDB
    response = users_table.put_item(
        Item={
            'userEmail': user.user_email,
            'isApprover': user.is_approver,
            'isSuperUser': user.is_super_user,
            'createdAt': user.created_at.isoformat(),
            'supervisionSpaceId': user.supervision_space_id
        }
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'User stored successfully!'})
    }


def make_approver(user_email):
    try:
        response = users_table.update_item(
            Key={"userEmail": user_email},
            UpdateExpression="set isApprover=:true",
            ExpressionAttributeValues={":true": True},
            ReturnValues="UPDATED_NEW",
        )
    except:
        print(f"Unable to update user {user_email}")


def make_super_user(user_email):
    try:
        response = users_table.update_item(
            Key={"userEmail": user_email},
            UpdateExpression="set isSuperUser=:true",
            ExpressionAttributeValues={":true": True},
            ReturnValues="UPDATED_NEW",
        )
    except:
        print(f"Unable to update user {user_email}")


def add_dummy_user_data():
    user_dummy = User(
        user_email="tester@test.com",
        )
    store_user(user_dummy)


def get_user_data(user_email):
    """ Return a json with user data """
    response = users_table.get_item(Key={"userEmail": user_email})
    try:
        return response["Item"]
    except:
        print(f"User {user_email} not found in table")


def delete_user_data(user_email):
    response = users_table.delete_item(Key={"userEmail": user_email})
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'User deleted successfully!'})
    }
