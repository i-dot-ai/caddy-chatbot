from caddy.utils.tables import offices_table, users_table
from caddy.models.core import User

from datetime import datetime

from boto3.dynamodb.conditions import Attr
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()


@xray_recorder.capture()
def check_domain_status(domain: str):
    """
    Checks if the domain is enrolled with Caddy
    """
    domain_registered = offices_table.get_item(Key={"emailDomain": domain})
    if "Item" in domain_registered:
        return True
    else:
        return False


@xray_recorder.capture()
def check_user_status(user: str):
    """
    Checks if the user is registered with Caddy
    """
    user_registered = users_table.get_item(Key={"userEmail": user})
    if "Item" in user_registered:
        return True
    else:
        return False


@xray_recorder.capture()
def get_designated_supervisor_space(user: str):
    """
    Gets the registered supervisor space for a user
    """
    user_details_response = users_table.get_item(Key={"userEmail": user})

    if "Item" in user_details_response:
        return user_details_response["Item"]["supervisionSpaceId"]
    else:
        return "Unknown"


@xray_recorder.capture()
def register_user(user, role, supervisor_space_id):
    match role:
        case "Supervisor":
            isApprover = True
        case "Adviser":
            isApprover = False

    user = User(
        user_email=user,
        is_approver=isApprover,
        is_super_user=False,
        created_at=datetime.now(),
        supervision_space_id=supervisor_space_id,
    )

    users_table.put_item(
        Item={
            "userEmail": user.user_email,
            "isApprover": user.is_approver,
            "isSuperUser": False,
            "createdAt": user.created_at.isoformat(),
            "supervisionSpaceId": user.supervision_space_id,
        }
    )


@xray_recorder.capture()
def remove_user(user):
    users_table.delete_item(Key={"userEmail": user})


@xray_recorder.capture()
def list_users(supervision_space_id):
    response = users_table.scan(
        FilterExpression=Attr("supervisionSpaceId").eq(supervision_space_id)
    )

    user_list = response["Items"]

    supervision_users = []

    for user in user_list:
        match user["isApprover"]:
            case False:
                role = "Adviser"
            case True:
                role = "Supervisor"
        user_info = f"{user['userEmail']}: {role}"
        supervision_users.append(f"{user_info}\n")

    supervision_users = "".join(supervision_users)

    return supervision_users
