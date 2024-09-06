import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pydantic
from pydantic.types import StrictBool


# === Data Models ===
class User(pydantic.BaseModel):
    user_email: str
    activeCall: StrictBool = False
    is_approver: StrictBool = False
    is_super_user: StrictBool = False
    created_at: datetime = datetime.now()
    supervision_space_id: str


class UserMessage(pydantic.BaseModel):
    message_id: Union[str, None] = None
    conversation_id: Union[str, None] = None
    thread_id: Union[str, None] = None
    client: str
    user_email: str
    message: str
    message_sent_timestamp: str
    message_received_timestamp: datetime


class LlmResponse(pydantic.BaseModel):
    response_id: str = str(uuid.uuid4())
    message_id: str
    thread_id: str
    llm_prompt: str
    llm_answer: str
    llm_response_json: Union[pydantic.Json, None] = None
    llm_prompt_timestamp: datetime
    llm_response_timestamp: datetime
    route: str
    context: Union[List[Any], None]


class SupervisionEvent(pydantic.BaseModel):
    type: str
    source_client: str
    user: str
    llmPrompt: str
    llm_answer: str
    llm_response_json: pydantic.Json
    conversation_id: str
    thread_id: str
    message_id: str
    approver_received_timestamp: Union[datetime, None] = None
    response_id: str


class ApprovalEvent(pydantic.BaseModel):
    response_id: str
    thread_id: str
    approver_email: str
    approved: Union[bool, None] = None
    approval_timestamp: Union[datetime, None] = None
    user_response_timestamp: datetime
    supervisor_message: Union[str, None] = None


class CaddyMessageEvent(pydantic.BaseModel):
    type: str
    user: str
    name: str
    space_id: str
    thread_id: Optional[str] = None
    message_id: str
    message_string: str
    source_client: str
    timestamp: datetime
    teams_conversation: Optional[Dict[str, str]] = None
    teams_from: Optional[Dict[str, str]] = None
    teams_recipient: Optional[Dict[str, str]] = None
    teams_service_url: Optional[str] = None


class ProcessChatMessageEvent(pydantic.BaseModel):
    type: str
    user: str
    name: str
    space_id: str
    thread_id: str
    message_id: str
    message_string: str
    source_client: str
    timestamp: datetime
