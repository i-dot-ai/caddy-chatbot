# --- Status Messages --- #

PROCESSING = "*Status:* _*Processing*_"

GENERATING_RESPONSE = {"text": "*Status:* _*Generating response*_ "}

AWAITING_APPROVAL = {"text": "*Status:* _*Awaiting approval*_"}

# --- Google Chat Messages ---

DOMAIN_NOT_ENROLLED = {
    "text": "Caddy is not currently available for this domain. Please contact your administrator for more information."
}

USER_NOT_ENROLLED = {
    "text": "Caddy is not currently registered for you. Please contact your administrator for support in onboarding to Caddy"
}

INTRODUCE_CADDY_IN_DM = {
    "text": "Hi, I'm Caddy! I'm an AI support for Citizens Advice advisers, I'm here to help give advice to support in resolving your client queries. \n *To get started just send me a query*"
}

INTRODUCE_CADDY_IN_SPACE = "Hi, thank you for adding me to {space_name}, I'm Caddy! I'm an AI support for Citizens Advice advisers, I'm here to help give advice to support in resolving your client queries. \n\n *Just remember to type `@Caddy` at the start of your query if you would like my help.*"

SURVEY_ALREADY_COMPLETED = {
    "text": "_*Call thread has closed, please start a new call thread*_"
}

PII_DETECTED = '<b><font color="#FF0000">PII DETECTED</font><b> <i>Please ensure all queries to Caddy are anonymised. \n\n Choose whether to proceed anyway or edit your original query<i>'

INTRODUCE_CADDY_SUPERVISOR_IN_DM = {
    "text": "Hi, I'm the supervisor assistant for Caddy! Caddy is an AI support for Citizens Advice advisers. \n *To get started you will need to register the advisers into your supervision space so their messages come to you, you can do this by typing `/addUser` into the chat, other user management functionality can be seen using /help*"
}

INTRODUCE_CADDY_SUPERVISOR_IN_SPACE = "Hi, thank you for adding me to {space_name}, I'm the supervisor assistant for Caddy! Caddy is an AI support for Citizens Advice advisers. \n\nCaddy uses information from the below sites to form answers: \nGOV UK \nCitizens Advice \nAdviserNet \n\n*To get started you will need to register the advisers into your supervision space so their messages come to you, you can do this by typing `/addUser` into the chat, other user management functionality can be seen using `/help`*"

# --- Google Chat Dialogs --- #

SUCCESS_DIALOG = {
    "action_response": {
        "type": "DIALOG",
        "dialog_action": {"action_status": "OK"},
    }
}

ADD_USER_DIALOG = {
    "action_response": {
        "type": "DIALOG",
        "dialog_action": {
            "dialog": {
                "body": {
                    "sections": [
                        {
                            "header": "Onboard a new user to Caddy",
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": "To allow a new user to join Caddy within your organisation register their email below and select their permissions"
                                    }
                                },
                                {
                                    "textInput": {
                                        "label": "Email",
                                        "type": "SINGLE_LINE",
                                        "name": "email",
                                    }
                                },
                                {
                                    "selectionInput": {
                                        "type": "RADIO_BUTTON",
                                        "label": "Role",
                                        "name": "role",
                                        "items": [
                                            {
                                                "text": "Adviser",
                                                "value": "Adviser",
                                                "selected": True,
                                            },
                                            {
                                                "text": "Supervisor",
                                                "value": "Supervisor",
                                                "selected": False,
                                            },
                                        ],
                                    }
                                },
                                {
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "Add User",
                                                "onClick": {
                                                    "action": {
                                                        "function": "receiveDialog"
                                                    }
                                                },
                                            }
                                        ]
                                    },
                                    "horizontalAlignment": "END",
                                },
                            ],
                        }
                    ]
                }
            }
        },
    }
}

REMOVE_USER_DIALOG = {
    "action_response": {
        "type": "DIALOG",
        "dialog_action": {
            "dialog": {
                "body": {
                    "sections": [
                        {
                            "header": "Remove a user from Caddy",
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": "Input the email of the user whos access to Caddy supervision within your organisation you would like to revoke"
                                    }
                                },
                                {
                                    "textInput": {
                                        "label": "Email",
                                        "type": "SINGLE_LINE",
                                        "name": "email",
                                    }
                                },
                                {
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "Remove User",
                                                "onClick": {
                                                    "action": {
                                                        "function": "receiveDialog"
                                                    }
                                                },
                                            }
                                        ]
                                    },
                                    "horizontalAlignment": "END",
                                },
                            ],
                        }
                    ]
                }
            }
        },
    }
}

HELPER_DIALOG = {
    "action_response": {
        "type": "DIALOG",
        "dialog_action": {
            "dialog": {
                "body": {
                    "sections": [
                        {
                            "header": "Helper dialog for Caddy Supervisor",
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": "Adding a New User:\n\nTo add a new user under your supervision space, use the command /addUser.\nExample: /addUser\n\nRemoving User Access:\n\nIf you need to revoke access for a user, use the /removeUser command.\nExample: /removeUser\n\nListing Registered Users:\n\nTo view a list of users currently registered under your supervision, use the /listUsers command.\nThis command will display a comprehensive list, making it easy to manage and monitor user access.\nExample: /listUsers"
                                    }
                                }
                            ],
                        }
                    ]
                }
            }
        },
    }
}
