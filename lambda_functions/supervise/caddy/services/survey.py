from caddy.utils.tables import offices_table
import json


def get_survey(user):
    user_workspace_variables = get_user_workspace_variables(user)

    post_call_module = user_workspace_variables["end_of_conversation"][0][
        "module_arguments"
    ]

    post_call_survey_questions = post_call_module["questions"]
    post_call_survey_values = post_call_module["values"]

    return post_call_survey_questions, post_call_survey_values


def get_user_workspace_variables(user_email: str):
    """Takes a user table, and retrieves variables for user workspace"""

    email_domain = user_email.split("@")[1]

    # find the relevant office in the table, and return their variable dictionary

    response = offices_table.get_item(Key={"emailDomain": email_domain})

    # Convert the JSON string back to dictionary
    workspace_vars = json.loads(response["Item"]["workspaceVars"])

    return workspace_vars
