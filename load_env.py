# load_env.py
import os
from dotenv import load_dotenv

load_dotenv()

if os.environ.get('LOCAL_DEV', 'false').lower() == 'true':
    print ('defining env vars in .py')
    load_dotenv(verbose=True)
    print(os.environ.get('LOCAL_DEV'))
    print(os.environ.get('ANTHROPIC_API_KEY'))