import uuid
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

import pydantic
from pydantic.types import StrictBool

# === Data Models === #


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
    user_email: Union[str, None] = None
    message: str
    message_sent_timestamp: str
    message_received_timestamp: datetime
    status_message_id: Union[str, None] = None
    teams_conversation: Optional[Dict[Any, Any]] = None
    teams_from: Optional[Dict[str, str]] = None
    teams_recipient: Optional[Dict[str, str]] = None

    @property
    def space_id(self):
        return self.conversation_id


class LlmResponse(pydantic.BaseModel):
    response_id: str = str(uuid.uuid4())
    message_id: str
    thread_id: str | None = None
    llm_prompt: str
    llm_answer: str
    llm_response_json: Union[pydantic.Json, None] = None
    llm_prompt_timestamp: datetime
    llm_response_timestamp: datetime
    route: str
    context: Union[List[Any], None]
    supervision_message_id: Union[str, None] = None
    supervisor_thread_id: Union[str, None] = None


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
    status_message_id: Union[str, None] = None


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
    teams_conversation: Optional[Dict[Any, Any]] = None
    teams_from: Optional[Dict[str, str]] = None
    teams_recipient: Optional[Dict[str, str]] = None


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


class UserNotEnrolledException(Exception):
    pass


class NoSupervisionSpaceException(Exception):
    pass


# === Parser Models === #


class LLMOutput(pydantic.BaseModel):
    message: str = pydantic.Field(description="The main response message for the query")
    follow_up_questions: List[str] = pydantic.Field(
        description="List of up to 4 follow-up questions to improve the answer quality, potential answers are not to be included.",
    )


# === Caddy Interfaces === #


class ChatIntegration(ABC):
    """
    Interface that must be implemented by all chat integrations
    """

    @abstractmethod
    async def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming integration events
        """
        pass

    @abstractmethod
    async def send_message(
        self, space_id: str, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a message to the adviser chat space
        """
        pass

    @abstractmethod
    async def update_message(
        self, space_id: str, message_id: str, message: Dict[str, Any]
    ) -> None:
        """
        Update an existing message
        """
        pass

    @abstractmethod
    async def format_event_to_message(self, event: Dict[str, Any]) -> CaddyMessageEvent:
        """
        Convert integration specific event into platform agnostic CaddyMessageEvent
        """
        pass

    @abstractmethod
    def create_card(
        self, llm_output: str, context_sources: List[str]
    ) -> Dict[str, Any]:
        """
        Create integration specific response card
        """
        pass

    @abstractmethod
    async def send_status_update(
        self, message: UserMessage, status: str, message_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Send or update status message
        """
        pass

    @abstractmethod
    async def send_supervision_request(
        self,
        message_query: UserMessage,
        supervision_event: SupervisionEvent,
        response_card: Dict[str, Any],
    ) -> Tuple[str, str]:
        """
        Send request to supervision space

        Returns (thread_id, message_id)
        """
        pass

    @abstractmethod
    async def handle_supervision_approval(
        self,
        event: Dict[str, Any],
        approval_event: ApprovalEvent,
        response_card: Dict[str, Any],
    ) -> None:
        """
        Handle supervisor approval flow
        """
        pass

    @abstractmethod
    async def handle_supervision_rejection(
        self, event: Dict[str, Any], rejection_event: ApprovalEvent
    ) -> None:
        """
        Handle supervisor rejection flow
        """
        pass

    @abstractmethod
    async def send_follow_up_questions(
        self,
        message_query: UserMessage,
        llm_output: LLMOutput,
        context_sources: List[str],
        status_message_id: Optional[str] = None,
    ) -> None:
        """
        Send follow-up questions to user
        """
        pass

    @abstractmethod
    async def process_follow_up_answers(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process follow-up answers from user
        """
        pass

    @abstractmethod
    def create_supervision_card(
        self,
        user_email: str,
        supervision_event: SupervisionEvent,
        response_card: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create supervision card for review
        """
        pass

    @abstractmethod
    async def send_message_to_supervision_space(
        self, space_id: str, message: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Send message to supervision space

        Returns (thread_id, message_id)
        """
        pass

    @abstractmethod
    def update_message_in_supervision_space(
        self, space_id: str, message_id: str, message: Dict[str, Any]
    ) -> None:
        """
        Update message in supervision space
        """
        pass

    @abstractmethod
    def convert_to_client_friendly(
        self, card_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert response to client friendly format
        """
        pass

    @abstractmethod
    def create_pii_warning(
        self, message: str, original_event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create PII warning card
        """
        pass

    # === user management methods === #
    @abstractmethod
    async def add_user(self, event: Dict[str, Any]) -> None:
        """
        Add user to Caddy
        """
        pass

    @abstractmethod
    async def remove_user(self, event: Dict[str, Any]) -> None:
        """
        Remove user from Caddy
        """
        pass

    @abstractmethod
    async def list_users(self, space_id: str) -> Dict[str, Any]:
        """
        List users in space
        """
        pass
