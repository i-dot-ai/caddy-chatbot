import json

# --- Google Chat Messages ---

MESSAGES = {
    "domain_not_enrolled": json.dumps(
        {
            "text": "Caddy is not currently available for this domain. Please contact your administrator for more information."
        }
    ),
    "user_not_registered": json.dumps(
        {
            "text": "User is not registered, please contact your administrator for support in onboarding to Caddy"
        }
    ),
    "introduce_caddy_supervisor_DM": json.dumps(
        {
            "text": "Hi, I'm the supervisor assistant for Caddy! Caddy is an AI support for Citizens Advice advisers. \n *To get started you will need to register the advisers into your supervision space so their messages come to you, you can do this by typing `/addUser` into the chat, other user management functionality can be seen using /help*"
        }
    ),
    "introduce_caddy_supervisor_SPACE": "Hi, thank you for adding me to {space}, I'm the supervisor assistant for Caddy! Caddy is an AI support for Citizens Advice advisers. \n\nCaddy uses information from the below sites to form answers: \nGOV UK \nCitizens Advice \nAdviserNet \n\n*To get started you will need to register the advisers into your supervision space so their messages come to you, you can do this by typing `/addUser` into the chat, other user management functionality can be seen using `/help`*",
    "pii_detected": '<b><font color="#FF0000">PII DETECTED</font><b> <i>Please ensure all queries to Caddy are anonymised. \n\n Choose whether to proceed anyway or edit your original query<i>',
}
