import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class WhatsAppConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    access_token: str = ""
    phone_number_id: str = ""
    business_account_id: str = ""
    webhook_verify_token: str = ""
    webhook_url: str = ""
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    # Integração via n8n: quando configurado, o CRM enviará outbound messages para esta URL
    use_n8n: bool = False
    n8n_webhook_url: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WhatsAppConfigUpdate(BaseModel):
    access_token: Optional[str] = None
    phone_number_id: Optional[str] = None
    business_account_id: Optional[str] = None
    webhook_verify_token: Optional[str] = None
    webhook_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    use_n8n: Optional[bool] = None
    n8n_webhook_url: Optional[str] = None
