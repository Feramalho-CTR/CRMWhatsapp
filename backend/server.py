from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
from passlib.context import CryptContext
import hashlib

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Define Models
class UserRole(BaseModel):
    name: str  # "admin" ou "agent"

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    full_name: Optional[str] = None
    role: str  # "admin" ou "agent"
    status: str = "offline"  # "online", "busy", "paused", "offline"
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WhatsAppConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    access_token: str = ""
    phone_number_id: str = ""
    business_account_id: str = ""
    webhook_verify_token: str = ""
    webhook_url: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WhatsAppConfigUpdate(BaseModel):
    access_token: Optional[str] = None
    phone_number_id: Optional[str] = None
    business_account_id: Optional[str] = None
    webhook_verify_token: Optional[str] = None
    webhook_url: Optional[str] = None

class AgentStatus(BaseModel):
    agent_id: str
    status: str  # "online", "busy", "paused", "offline"

class AgentPerformance(BaseModel):
    agent_id: str
    agent_name: str
    total_conversations: int
    avg_response_time_minutes: float
    conversations_finished_today: int
    status: str
    last_activity: datetime

class ServiceMetrics(BaseModel):
    conversation_id: str
    client_phone: str
    client_name: Optional[str]
    agent_id: str
    agent_name: str
    service_duration_minutes: Optional[float]
    started_at: datetime
    finished_at: Optional[datetime]

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

class Client(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phone_number: str
    name: Optional[str] = None
    status: str = "bot"  # "bot", "human", "waiting", "finished"
    assigned_agent: Optional[str] = None
    agent_name: Optional[str] = None  # Nome do agente para exibição
    service_started_at: Optional[datetime] = None
    service_finished_at: Optional[datetime] = None
    last_interaction: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ClientCreate(BaseModel):
    phone_number: str
    name: Optional[str] = None

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    assigned_agent: Optional[str] = None

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    sender_type: str  # "client", "bot", "agent"
    sender_id: Optional[str] = None  # ID do agente se sender_type for "agent"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MessageCreate(BaseModel):
    client_id: str
    sender_type: str
    sender_id: Optional[str] = None
    content: str

class Conversation(BaseModel):
    client: Client
    messages: List[Message]
    unread_count: int = 0

# Helper functions
def verify_password(plain_password, hashed_password):
    # Simple hash verification for MVP - use bcrypt in production
    import hashlib
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

def get_password_hash(password):
    # Simple hash for MVP - use bcrypt in production
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await db.users.find_one({"username": username})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return User(**user)

# Auth routes
@api_router.post("/auth/register", response_model=User)
async def register_user(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"username": user_data.username})
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    # Hash password and create user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        username=user_data.username,
        email=user_data.email,
        role=user_data.role
    )
    
    # Store in DB
    user_dict = user.dict()
    user_dict["password"] = hashed_password
    await db.users.insert_one(user_dict)
    
    return user

@api_router.post("/auth/login", response_model=Token)
async def login_user(user_credentials: UserLogin):
    user = await db.users.find_one({"username": user_credentials.username})
    if not user or not verify_password(user_credentials.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    user_obj = User(**user)
    return Token(access_token=access_token, token_type="bearer", user=user_obj)

@api_router.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

# Admin routes
async def admin_required(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

@api_router.get("/admin/users", response_model=List[User])
async def get_all_users(admin_user: User = Depends(admin_required)):
    users = await db.users.find().to_list(1000)
    return [User(**user) for user in users]

@api_router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, admin_user: User = Depends(admin_required)):
    # Prevent admin from deleting themselves
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account"
        )
    
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"success": True, "message": "User deleted successfully"}

@api_router.get("/admin/whatsapp-config", response_model=WhatsAppConfig)
async def get_whatsapp_config(admin_user: User = Depends(admin_required)):
    config = await db.whatsapp_config.find_one({})
    if not config:
        # Create default config
        default_config = WhatsAppConfig()
        await db.whatsapp_config.insert_one(default_config.dict())
        return default_config
    return WhatsAppConfig(**config)

@api_router.put("/admin/whatsapp-config", response_model=WhatsAppConfig)
async def update_whatsapp_config(config_update: WhatsAppConfigUpdate, admin_user: User = Depends(admin_required)):
    # Get existing config or create new one
    existing_config = await db.whatsapp_config.find_one({})
    if not existing_config:
        new_config = WhatsAppConfig()
        config_dict = new_config.dict()
        # Update with provided values
        for key, value in config_update.dict(exclude_unset=True).items():
            if value is not None:
                config_dict[key] = value
        config_dict["updated_at"] = datetime.now(timezone.utc)
        await db.whatsapp_config.insert_one(config_dict)
        return WhatsAppConfig(**config_dict)
    
    # Update existing config
    update_data = {}
    for key, value in config_update.dict(exclude_unset=True).items():
        if value is not None:
            update_data[key] = value
    
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        await db.whatsapp_config.update_one(
            {"id": existing_config["id"]},
            {"$set": update_data}
        )
    
    updated_config = await db.whatsapp_config.find_one({"id": existing_config["id"]})
    return WhatsAppConfig(**updated_config)

@api_router.post("/admin/test-whatsapp")
async def test_whatsapp_connection(admin_user: User = Depends(admin_required)):
    """Test WhatsApp API connection"""
    config = await db.whatsapp_config.find_one({})
    if not config or not config.get("access_token") or not config.get("phone_number_id"):
        raise HTTPException(
            status_code=400,
            detail="WhatsApp configuration incomplete. Please configure Access Token and Phone Number ID."
        )
    
    # Here you would implement actual WhatsApp API test
    # For now, we'll return a mock success response
    try:
        # Mock API test - replace with actual WhatsApp API call
        # import requests
        # url = f"https://graph.facebook.com/v18.0/{config['phone_number_id']}"
        # headers = {"Authorization": f"Bearer {config['access_token']}"}
        # response = requests.get(url, headers=headers)
        # return {"success": response.status_code == 200}
        
        return {"success": True, "message": "Connection test successful (mock)"}
    except Exception as e:
        return {"success": False, "message": f"Connection test failed: {str(e)}"}

@api_router.put("/admin/whatsapp-config")
async def save_whatsapp_config(config: WhatsAppConfigUpdate, admin_user: User = Depends(admin_required)):
    # Convert to dict and filter out None values
    config_dict = {k: v for k, v in config.dict().items() if v is not None}
    config_dict["updated_at"] = datetime.now(timezone.utc)
    
    # Update or insert config
    existing = await db.whatsapp_config.find_one({})
    if existing:
        await db.whatsapp_config.update_one({}, {"$set": config_dict})
    else:
        config_dict["id"] = str(uuid.uuid4())
        await db.whatsapp_config.insert_one(config_dict)
    
    return {"success": True, "message": "Configuration saved successfully"}

@api_router.get("/admin/agents-performance", response_model=List[AgentPerformance])
async def get_agents_performance(admin_user: User = Depends(admin_required)):
    """Get performance metrics for all agents"""
    agents = await db.users.find({"role": "agent"}).to_list(1000)
    performance_list = []
    
    for agent in agents:
        agent_id = agent["id"]
        
        # Count total conversations handled by this agent
        total_conversations = await db.clients.count_documents({"assigned_agent": agent_id})
        
        # Count conversations finished today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        conversations_today = await db.clients.count_documents({
            "assigned_agent": agent_id,
            "status": "finished",
            "service_finished_at": {"$gte": today_start}
        })
        
        # Calculate average response time
        finished_conversations = await db.clients.find({
            "assigned_agent": agent_id,
            "service_started_at": {"$exists": True},
            "service_finished_at": {"$exists": True}
        }).to_list(1000)
        
        total_duration = 0
        count = 0
        for conv in finished_conversations:
            if conv.get("service_started_at") and conv.get("service_finished_at"):
                start = conv["service_started_at"]
                end = conv["service_finished_at"]
                duration = (end - start).total_seconds() / 60  # minutes
                total_duration += duration
                count += 1
        
        avg_response_time = total_duration / count if count > 0 else 0
        
        performance = AgentPerformance(
            agent_id=agent_id,
            agent_name=agent["username"],
            total_conversations=total_conversations,
            avg_response_time_minutes=round(avg_response_time, 2),
            conversations_finished_today=conversations_today,
            status=agent.get("status", "offline"),
            last_activity=agent.get("last_activity", agent["created_at"])
        )
        performance_list.append(performance)
    
    return performance_list

@api_router.get("/admin/service-metrics", response_model=List[ServiceMetrics])
async def get_service_metrics(admin_user: User = Depends(admin_required)):
    """Get detailed service metrics"""
    # Get finished conversations from last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    finished_conversations = await db.clients.find({
        "status": "finished",
        "service_finished_at": {"$gte": thirty_days_ago},
        "assigned_agent": {"$exists": True}
    }).to_list(1000)
    
    metrics_list = []
    for conv in finished_conversations:
        # Get agent name
        agent = await db.users.find_one({"id": conv["assigned_agent"]})
        agent_name = agent["username"] if agent else "Unknown"
        
        # Calculate duration
        duration = None
        if conv.get("service_started_at") and conv.get("service_finished_at"):
            start = conv["service_started_at"]
            end = conv["service_finished_at"]
            duration = (end - start).total_seconds() / 60  # minutes
        
        metric = ServiceMetrics(
            conversation_id=conv["id"],
            client_phone=conv["phone_number"],
            client_name=conv.get("name"),
            agent_id=conv["assigned_agent"],
            agent_name=agent_name,
            service_duration_minutes=round(duration, 2) if duration else None,
            started_at=conv["service_started_at"],
            finished_at=conv["service_finished_at"]
        )
        metrics_list.append(metric)
    
    return sorted(metrics_list, key=lambda x: x.finished_at, reverse=True)

# Agent status routes
@api_router.put("/agent/status")
async def update_agent_status(status_data: AgentStatus, current_user: User = Depends(get_current_user)):
    """Update agent status (online, busy, paused, offline)"""
    if current_user.id != status_data.agent_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Can only update your own status")
    
    update_data = {
        "status": status_data.status,
        "last_activity": datetime.now(timezone.utc)
    }
    
    await db.users.update_one(
        {"id": status_data.agent_id},
        {"$set": update_data}
    )
    
    return {"success": True, "status": status_data.status}

@api_router.get("/agent/my-status")
async def get_my_status(current_user: User = Depends(get_current_user)):
    """Get current user status"""
    user = await db.users.find_one({"id": current_user.id})
    return {"status": user.get("status", "offline")}

@api_router.put("/clients/{client_id}/finish-service")
async def finish_service(client_id: str, current_user: User = Depends(get_current_user)):
    """Mark service as finished"""
    client = await db.clients.find_one({"id": client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if user is assigned to this client or is admin
    if client.get("assigned_agent") != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to finish this service")
    
    update_data = {
        "status": "finished",
        "service_finished_at": datetime.now(timezone.utc)
    }
    
    # Set service_started_at if not set (fallback)
    if not client.get("service_started_at"):
        update_data["service_started_at"] = client["created_at"]
    
    await db.clients.update_one(
        {"id": client_id},
        {"$set": update_data}
    )
    
    # Update agent status to online (available for new conversations)
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"status": "online", "last_activity": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "message": "Service finished successfully"}

@api_router.put("/clients/{client_id}/accept-service")
async def accept_service(client_id: str, current_user: User = Depends(get_current_user)):
    """Accept service for a client"""
    client = await db.clients.find_one({"id": client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if agent is available
    user = await db.users.find_one({"id": current_user.id})
    if user.get("status") not in ["online"]:
        raise HTTPException(status_code=400, detail="Agent must be online to accept service")
    
    update_data = {
        "status": "human",
        "assigned_agent": current_user.id,
        "service_started_at": datetime.now(timezone.utc)
    }
    
    await db.clients.update_one(
        {"id": client_id},
        {"$set": update_data}
    )
    
    # Update agent status to busy
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"status": "busy", "last_activity": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "message": "Service accepted successfully"}

# Profile routes
@api_router.put("/profile/update", response_model=User)
async def update_profile(profile_data: UserUpdate, current_user: User = Depends(get_current_user)):
    """Update current user profile"""
    update_data = {k: v for k, v in profile_data.dict().items() if v is not None}
    
    # Check if username is unique (if being updated)
    if "username" in update_data:
        existing_user = await db.users.find_one({
            "username": update_data["username"],
            "id": {"$ne": current_user.id}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email is unique (if being updated)
    if "email" in update_data:
        existing_user = await db.users.find_one({
            "email": update_data["email"],
            "id": {"$ne": current_user.id}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    if update_data:
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": update_data}
        )
    
    updated_user = await db.users.find_one({"id": current_user.id})
    return User(**updated_user)

@api_router.put("/profile/change-password")
async def change_password(password_data: PasswordChange, current_user: User = Depends(get_current_user)):
    """Change user password"""
    user = await db.users.find_one({"id": current_user.id})
    if not verify_password(password_data.current_password, user["password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    new_hashed_password = get_password_hash(password_data.new_password)
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"password": new_hashed_password}}
    )
    
    return {"success": True, "message": "Password changed successfully"}

@api_router.put("/admin/users/{user_id}", response_model=User)
async def update_user(user_id: str, user_data: UserUpdate, admin_user: User = Depends(admin_required)):
    """Update user by admin"""
    # Prevent admin from updating themselves through this endpoint
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Use profile update endpoint for your own data")
    
    update_data = {k: v for k, v in user_data.dict().items() if v is not None}
    
    # Check if username is unique (if being updated)
    if "username" in update_data:
        existing_user = await db.users.find_one({
            "username": update_data["username"],
            "id": {"$ne": user_id}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email is unique (if being updated)
    if "email" in update_data:
        existing_user = await db.users.find_one({
            "email": update_data["email"],
            "id": {"$ne": user_id}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    updated_user = await db.users.find_one({"id": user_id})
    return User(**updated_user)

# Client routes
@api_router.get("/clients", response_model=List[Client])
async def get_clients(current_user: User = Depends(get_current_user)):
    clients = await db.clients.find().to_list(1000)
    return [Client(**client) for client in clients]

@api_router.post("/clients", response_model=Client)
async def create_client(client_data: ClientCreate, current_user: User = Depends(get_current_user)):
    # Check if client already exists
    existing_client = await db.clients.find_one({"phone_number": client_data.phone_number})
    if existing_client:
        raise HTTPException(
            status_code=400,
            detail="Client with this phone number already exists"
        )
    
    client = Client(**client_data.dict())
    await db.clients.insert_one(client.dict())
    return client

@api_router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, client_data: ClientUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in client_data.dict().items() if v is not None}
    
    result = await db.clients.update_one(
        {"id": client_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    
    updated_client = await db.clients.find_one({"id": client_id})
    return Client(**updated_client)

# Message routes
@api_router.get("/clients/{client_id}/messages", response_model=List[Message])
async def get_client_messages(client_id: str, current_user: User = Depends(get_current_user)):
    messages = await db.messages.find({"client_id": client_id}).sort("timestamp", 1).to_list(1000)
    return [Message(**message) for message in messages]

@api_router.post("/messages", response_model=Message)
async def create_message(message_data: MessageCreate, current_user: User = Depends(get_current_user)):
    message = Message(**message_data.dict())
    await db.messages.insert_one(message.dict())
    
    # Update client's last interaction
    await db.clients.update_one(
        {"id": message_data.client_id},
        {"$set": {"last_interaction": message.timestamp}}
    )
    
    return message

@api_router.get("/conversations", response_model=List[Conversation])
async def get_conversations(current_user: User = Depends(get_current_user)):
    clients = await db.clients.find().sort("last_interaction", -1).to_list(100)
    conversations = []
    
    for client_data in clients:
        # Get agent info if assigned
        agent_name = None
        if client_data.get("assigned_agent"):
            agent = await db.users.find_one({"id": client_data["assigned_agent"]})
            if agent:
                agent_name = agent.get("full_name") or agent.get("username")
        
        client = Client(**client_data)
        # Add agent_name to client data
        client_dict = client.dict()
        client_dict["agent_name"] = agent_name
        
        messages = await db.messages.find({"client_id": client.id}).sort("timestamp", -1).limit(1).to_list(1)
        messages_list = [Message(**msg) for msg in messages]
        
        conversation = Conversation(
            client=Client(**client_dict),
            messages=messages_list,
            unread_count=0  # TODO: implement unread logic
        )
        conversations.append(conversation)
    
    return conversations

# Mock WhatsApp integration routes
@api_router.post("/whatsapp/send")
async def send_whatsapp_message(message_data: MessageCreate, current_user: User = Depends(get_current_user)):
    """Mock endpoint para simular envio via WhatsApp API"""
    
    # Save message to database
    message = Message(**message_data.dict())
    await db.messages.insert_one(message.dict())
    
    # Update client's last interaction
    await db.clients.update_one(
        {"id": message_data.client_id},
        {"$set": {"last_interaction": message.timestamp}}
    )
    
    # Mock response (in real implementation, this would call WhatsApp Business API)
    return {
        "success": True,
        "message_id": message.id,
        "status": "sent",
        "note": "This is a mock response. Replace with actual WhatsApp API integration."
    }

@api_router.post("/whatsapp/webhook")
async def whatsapp_webhook(payload: dict):
    """Mock webhook para receber mensagens do WhatsApp"""
    
    # Extract data from webhook payload (this is mock structure)
    phone_number = payload.get("from", "unknown")
    content = payload.get("text", "")
    
    # Find or create client
    client = await db.clients.find_one({"phone_number": phone_number})
    if not client:
        new_client = Client(phone_number=phone_number, name=f"Cliente {phone_number}")
        await db.clients.insert_one(new_client.dict())
        client_id = new_client.id
    else:
        client_id = client["id"]
    
    # Create message
    message = Message(
        client_id=client_id,
        sender_type="client",
        content=content
    )
    await db.messages.insert_one(message.dict())
    
    # Update client's last interaction
    await db.clients.update_one(
        {"id": client_id},
        {"$set": {"last_interaction": message.timestamp}}
    )
    
    return {"success": True, "message": "Message received"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# Create default admin user on startup
@app.on_event("startup")
async def create_default_admin():
    try:
        # Check if users exist and update them to have status and full_name fields
        existing_users = await db.users.find({}).to_list(1000)
        for user in existing_users:
            update_fields = {}
            if "status" not in user:
                update_fields["status"] = "offline"
                update_fields["last_activity"] = datetime.now(timezone.utc)
            if "full_name" not in user:
                update_fields["full_name"] = user.get("username", "")
            
            if update_fields:
                await db.users.update_one(
                    {"id": user["id"]},
                    {"$set": update_fields}
                )
        
        # Check if admin exists
        admin_exists = await db.users.find_one({"username": "admin"})
        if not admin_exists:
            # Create admin user
            admin_user = User(
                username="admin",
                email="admin@crm.com",
                full_name="Administrador",
                role="admin",
                status="offline"
            )
            
            admin_dict = admin_user.dict()
            admin_dict["password"] = get_password_hash("admin123")
            await db.users.insert_one(admin_dict)
            logger.info("Default admin user created: username=admin, password=admin123")
        
        # Check if agent exists
        agent_exists = await db.users.find_one({"username": "agent1"})
        if not agent_exists:
            # Create sample agent
            agent_user = User(
                username="agent1",
                email="agent1@crm.com",
                role="agent",
                status="offline"
            )
            
            agent_dict = agent_user.dict()
            agent_dict["password"] = get_password_hash("agent123")
            await db.users.insert_one(agent_dict)
            logger.info("Sample agent user created: username=agent1, password=agent123")
            
    except Exception as e:
        logger.error(f"Error creating default users: {e}")