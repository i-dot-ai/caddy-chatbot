from models import idempotent_table
import json

def idempotent():
    def decorator(func):
      def wrapper(event, *args, **kwargs):
          message_id = event['message']['name']

          response = idempotent_table.get_item(
              Key={
                  'id': str(message_id)
                }
            )

          if 'Item' in response:
              match response['Item']['status']:
                  case 'IN_PROGRESS':
                      return None
                  case 'FAILED':
                      return func(event, *args, **kwargs)
          else:
            idempotent_table.put_item(
              Item={
                  'id': str(message_id),
                  'status': 'IN_PROGRESS'
                  }
            )
            return func(event, *args, **kwargs)
      return wrapper
    return decorator
