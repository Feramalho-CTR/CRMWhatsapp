import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class Client(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phone_number: str
    phone_normalized: Optional[str] = None
    name: Optional[str] = None
    display_name: Optional[str] = None
    status: str = "bot"  # "bot", "human", "waiting", "finished"
    assigned_agent: Optional[str] = None
    agent_name: Optional[str] = None  # Nome do agente para exibição
    service_started_at: Optional[datetime] = None
    service_finished_at: Optional[datetime] = None
    last_interaction: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    label: Optional[str] = None


class ClientCreate(BaseModel):
    phone_number: str
    name: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    assigned_agent: Optional[str] = None


class AssignClientRequest(BaseModel):
    agent_id: str
