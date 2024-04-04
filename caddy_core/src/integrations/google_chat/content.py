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
    "introduce_caddy_DM": json.dumps(
        {
            "text": "Hi, I'm Caddy! I'm an AI support for Citizens Advice advisers, I'm here to help give advice to support in resolving your client queries. \n *To get started just send me a query*"
        }
    ),
    "introduce_caddy_SPACE": "Hi, thank you for adding me to {space}, I'm Caddy! I'm an AI support for Citizens Advice advisers, I'm here to help give advice to support in resolving your client queries. \n\n *Just remember to type `@Caddy` at the start of your query if you would like my help.*",
    "pii_detected": '<b><font color="#FF0000">PII DETECTED</font><b> <i>Please ensure all queries to Caddy are anonymised. \n\n Choose whether to proceed anyway or edit your original query<i>',
}
