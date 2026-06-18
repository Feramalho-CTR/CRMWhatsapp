import uuid
from datetime import datetime, timezone
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from .client import Client


class ServiceMetrics(BaseModel):
    model_config = ConfigDict(extra='ignore')
    conversation_id: str
    client_phone: str
    client_name: Optional[str]
    agent_id: str
    agent_name: str
    service_duration_minutes: Optional[float]
    started_at: datetime
    finished_at: Optional[datetime]


class Message(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S_') + str(uuid.uuid4())[:8])
    client_id: str
    sender_type: str  # "client", "bot", "agent"
    sender_id: Optional[str] = None  # ID do agente se sender_type for "agent"
    sender_name: Optional[str] = None  # Nome amigável do remetente
    content: str
    message_type: str = "text"  # "text", "document", "image", "video", "audio", "sticker"
    media_metadata: Optional[dict] = None  # { "url": "...", "filename": "...", "mime_type": "..." }
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    external_response: Optional[dict] = None


class MessageCreate(BaseModel):
    client_id: str
    sender_type: str
    sender_id: Optional[str] = None
    content: str
    message_type: str = "text"
    media_metadata: Optional[dict] = None


class Conversation(BaseModel):
    client: Client
    messages: List[Message]
    unread_count: int = 0
