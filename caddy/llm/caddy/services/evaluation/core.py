import json
from caddy.utils.tables import offices_table
from caddy.services.evaluation.modules import module_registry


def get_user_workspace_variables(user_email: str):
    """Takes a user table, and retrieves variables for user workspace"""

    email_domain = user_email.split("@")[1]

    # find the relevant office in the table, and return their variable dictionary

    response = offices_table.get_item(Key={"emailDomain": email_domain})

    # Convert the JSON string back to dictionary
    workspace_vars = json.loads(response["Item"]["workspaceVars"])

    return workspace_vars


def execute_optional_modules(event, execution_time):
    """Executes optional modules linked to the user workspace"""

    suitable_time_strings = [
        "before_message_processed",
        "after_message_processed",
        "end_of_conversation",
    ]

    if execution_time not in suitable_time_strings:
        raise ValueError(
            f"Invalid execution time: {execution_time}. Must be one of {suitable_time_strings}"
        )
    continue_conversation = True

    user_email = event["user"]

    user_workspace_variables = get_user_workspace_variables(user_email)
    modules_to_use = user_workspace_variables[execution_time]

    module_outputs = {}
    for module in modules_to_use:
        module_name = module["module_name"]
        module_arguments = module["module_arguments"]

        try:
            module_func = module_registry[module_name]
        except KeyError:
            print(f"Module function '{module_name}' not found.")
            continue

        try:
            result = module_func(event=event, **module_arguments)
            module_outputs[module_name] = result

            if result[0] == "end_interaction":
                continue_conversation = False
        except Exception as e:
            print(f"Error occurred while executing module '{module_name}': {str(e)}")

    # this will be received from API
    module_outputs_json = json.dumps(module_outputs)

    return modules_to_use, module_outputs_json, continue_conversation


def add_workspace_variables_to_table(email_domain: str, workspace_vars: dict):
    """Finds the relevant office in the office table and adds the workspace variables"""

    workspace_vars_json = json.dumps(workspace_vars)

    response = offices_table.update_item(
        Key={"emailDomain": email_domain},
        UpdateExpression="set workspaceVars=:w",
        ExpressionAttributeValues={":w": workspace_vars_json},
        ReturnValues="UPDATED_NEW",
    )

    return response
