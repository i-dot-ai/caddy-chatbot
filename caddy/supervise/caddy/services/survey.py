from caddy.utils.tables import offices_table
from integrations.google_chat.responses import send_message_to_adviser_space
import json


def run_survey(user_email, adviser_space_id, thread_id):
    user_workspace_variables = get_user_workspace_variables(user_email)

    post_call_module = user_workspace_variables["end_of_conversation"][0][
        "module_arguments"
    ]

    post_call_survey_questions = post_call_module["questions"]
    post_call_survey_values = post_call_module["values"]

    survey_card = get_post_call_survey_card(
        post_call_survey_questions, post_call_survey_values
    )

    send_message_to_adviser_space(
        response_type="cardsV2",
        space_id=adviser_space_id,
        message=survey_card,
        thread_id=thread_id,
    )


def get_user_workspace_variables(user_email: str):
    """Takes a user table, and retrieves variables for user workspace"""

    email_domain = user_email.split("@")[1]

    # find the relevant office in the table, and return their variable dictionary

    response = offices_table.get_item(Key={"emailDomain": email_domain})

    # Convert the JSON string back to dictionary
    workspace_vars = json.loads(response["Item"]["workspaceVars"])

    return workspace_vars


def get_post_call_survey_card(post_call_survey_questions, post_call_survey_values):
    card = {
        "cardsV2": [
            {
                "cardId": "postCallSurvey",
                "card": {
                    "sections": [],
                },
            },
        ],
    }

    for question in post_call_survey_questions:
        section = {"widgets": []}

        question_section = {"textParagraph": {"text": question}}

        button_section = {"buttonList": {"buttons": []}}

        for value in post_call_survey_values:
            button_section["buttonList"]["buttons"].append(
                {
                    "text": value,
                    "onClick": {
                        "action": {
                            "function": "survey_response",
                            "parameters": [
                                {"key": "question", "value": question},
                                {"key": "response", "value": value},
                            ],
                        }
                    },
                }
            )

        section["widgets"].append(question_section)
        section["widgets"].append(button_section)

        card["cardsV2"][0]["card"]["sections"].append(section)

    return card
