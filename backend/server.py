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
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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
    role: str  # "admin" ou "agent"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "agent"

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
    status: str = "bot"  # "bot", "human", "waiting"
    assigned_agent: Optional[str] = None
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
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

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
        client = Client(**client_data)
        messages = await db.messages.find({"client_id": client.id}).sort("timestamp", -1).limit(1).to_list(1)
        messages_list = [Message(**msg) for msg in messages]
        
        conversation = Conversation(
            client=client,
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
        # Check if admin exists
        admin_exists = await db.users.find_one({"username": "admin"})
        if not admin_exists:
            admin_user = User(
                username="admin",
                email="admin@crm.com",
                role="admin"
            )
            
            admin_dict = admin_user.dict()
            admin_dict["password"] = get_password_hash("admin123")
            await db.users.insert_one(admin_dict)
            logger.info("Default admin user created: username=admin, password=admin123")
        
        # Create sample agent
        agent_exists = await db.users.find_one({"username": "agent1"})
        if not agent_exists:
            agent_user = User(
                username="agent1",
                email="agent1@crm.com",
                role="agent"
            )
            
            agent_dict = agent_user.dict()
            agent_dict["password"] = get_password_hash("agent123")
            await db.users.insert_one(agent_dict)
            logger.info("Sample agent user created: username=agent1, password=agent123")
            
    except Exception as e:
        logger.error(f"Error creating default users: {e}")