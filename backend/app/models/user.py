import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    uid: Optional[str] = None  # Firebase UID
    username: str
    email: str
    full_name: Optional[str] = None
    role: str = "agent"  # "admin" ou "agent"
    status: str = "offline"  # "online", "busy", "paused", "offline"
    is_active: bool = True  # Para controle de acesso sem exclusão
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentStatus(BaseModel):
    agent_id: str
    status: str  # "online", "busy", "paused", "offline"


class AgentPerformance(BaseModel):
    model_config = ConfigDict(extra='ignore')
    agent_id: str
    agent_name: str
    total_conversations: int
    avg_response_time_minutes: str  # Formato "MM:SS"
    conversations_finished_today: int
    status: str
    last_activity: Optional[datetime] = None


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    role: str = "agent"


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: User
