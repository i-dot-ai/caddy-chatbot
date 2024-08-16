import os
import boto3
from caddy_core.services.router import get_route

def get_prompt(prompt_name):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('PROMPTS_TABLE_NAME'))
    
    response = table.get_item(
        Key={
            'PromptName': prompt_name
        }
    )
    return response['Item']['Prompt'] if 'Item' in response else None


def retrieve_route_specific_augmentation(query):
    refresh_session_token()
    route = get_route(query).name
    
    prompt_name = f"{route.upper()}_PROMPT"
    route_specific_augmentation = get_prompt(prompt_name)
    
    if route_specific_augmentation is None:
        route_specific_augmentation = get_prompt('FALLBACK_PROMPT')
    
    return route_specific_augmentation, route

def refresh_session_token():
    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials.token is not None:
        os.environ["AWS_SESSION_TOKEN"] = credentials.token