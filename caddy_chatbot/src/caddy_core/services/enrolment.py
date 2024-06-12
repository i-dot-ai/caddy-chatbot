from caddy_core.utils.tables import offices_table, users_table
from caddy_core.models import User

from datetime import datetime

from boto3.dynamodb.conditions import Attr


def check_domain_status(domain: str):
    """
    Checks if the domain is enrolled with Caddy
    """
    office = offices_table.get_item(Key={"emailDomain": domain})
    if "Item" in office:
        return True, office["Item"]
    else:
        return False, None


def check_rct_status(office: dict):
    """
    Checks if the domain is part of the RCT
    """
    if "rctParticipant" in office:
        return office["rctParticipant"]
    return False


def check_user_status(user: str):
    """
    Checks if the user is registered with Caddy
    """
    user_registered = users_table.get_item(Key={"userEmail": user})
    if "Item" in user_registered:
        return True, user_registered["Item"]
    else:
        return False, None


def check_user_call_status(user_record: dict):
    """
    Checks if the user has an active call on Caddy
    """
    if "activeCall" in user_record:
        return user_record["activeCall"]
    return False


def check_user_role(user_record: dict):
    """
    Checks whether the user has the role of supervisor
    """
    if "isApprover" in user_record:
        return user_record["isApprover"]
    return False


def get_office_coverage(office: dict):
    """
    Gets areas covered for the office
    """
    coverage = ["England"]
    if "officeCoverage" in office:
        coverage = office["officeCoverage"]
    return coverage


def get_designated_supervisor_space(user: str):
    """
    Gets the registered supervisor space for a user
    """
    user_details_response = users_table.get_item(Key={"userEmail": user})

    if "Item" in user_details_response:
        return user_details_response["Item"]["supervisionSpaceId"]
    else:
        return "Unknown"


def register_user(user, role, supervisor_space_id):
    match role:
        case "Supervisor":
            isApprover = True
        case "Adviser":
            isApprover = False

    user = User(
        user_email=user,
        activeCall=False,
        is_approver=isApprover,
        is_super_user=False,
        created_at=datetime.now(),
        supervision_space_id=supervisor_space_id,
    )

    try:
        users_table.put_item(
            Item={
                "userEmail": user.user_email,
                "activeCall": False,
                "isApprover": user.is_approver,
                "isSuperUser": False,
                "createdAt": user.created_at.isoformat(),
                "supervisionSpaceId": user.supervision_space_id,
            }
        )
        return {"status": 200, "content": "user registration completed successfully"}
    except Exception as error:
        return {"status": 500, "content": f"user registration failed: {error}"}


def remove_user(user):
    try:
        users_table.delete_item(Key={"userEmail": user})
        return {"status": 200, "content": "user deletion completed successfully"}
    except Exception as error:
        return {"status": 500, "content": f"user deletion failed: {error}"}


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
