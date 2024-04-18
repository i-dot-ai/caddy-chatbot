from caddy_core.utils.tables import offices_table
import json
from typing import List, Tuple


def check_if_survey_required(user: str):
    """
    Checks whether survey questions are present in end of conversation modules
    """

    user_workspace_variables = get_user_workspace_variables(user)

    if "module_name" in user_workspace_variables["end_of_conversation"][0]:
        if (
            user_workspace_variables["end_of_conversation"][0]["module_name"]
            == "survey_questions"
        ):
            return True
        else:
            return False


def get_survey(user: str) -> Tuple[List[str], List[str]]:
    """
    Retrieve the post call survey questions and values for a user

    Args:
        user (str): The email of the user

    Returns:
        List[dict[str, List[str]]]: A list of questions and values for the survey
    """
    user_workspace_variables = get_user_workspace_variables(user)

    post_call_module = user_workspace_variables["end_of_conversation"][0][
        "module_arguments"
    ]

    post_call_survey_questions = post_call_module["questions"]

    return post_call_survey_questions


def get_user_workspace_variables(user_email: str):
    """Takes a user table, and retrieves variables for user workspace"""

    email_domain = user_email.split("@")[1]

    # find the relevant office in the table, and return their variable dictionary

    response = offices_table.get_item(Key={"emailDomain": email_domain})

    # Convert the JSON string back to dictionary
    workspace_vars = json.loads(response["Item"]["workspaceVars"])

    return workspace_vars
