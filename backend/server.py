import os
import asyncio
import json
import logging
import uuid
import re
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

import firebase_admin
import jwt
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import credentials, firestore, auth
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Inicializa Firebase Admin / Firestore
# Suporta duas formas de configuração:
# 1) Defina GOOGLE_APPLICATION_CREDENTIALS apontando para o arquivo JSON da conta de serviço
# 2) Ou defina a variável FIREBASE_CREDENTIALS_JSON com o conteúdo JSON da chave
FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')
FIREBASE_PROJECT = os.environ.get('FIREBASE_PROJECT')

firebase_app = None
try:
    if FIREBASE_CREDENTIALS_JSON:
        # carrega o JSON em memória e inicializa com o dict
        cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
        firebase_app = firebase_admin.initialize_app(cred)
    else:
        # Usa Application Default Credentials (funciona quando GOOGLE_APPLICATION_CREDENTIALS está setado)
        cred = credentials.ApplicationDefault()
        firebase_app = firebase_admin.initialize_app(cred, {'projectId': FIREBASE_PROJECT} if FIREBASE_PROJECT else None)
except Exception:
    # Tenta obter app já inicializado (por exemplo em ambiente GCP)
    try:
        firebase_app = firebase_admin.get_app()
    except Exception:
        firebase_app = None

# Cliente Firestore (síncrono). Vamos fornecer um wrapper async simples.
_firestore_client = firestore.client() if firebase_app is not None else None


def normalize_phone(phone: Optional[str]):
    """Return only digits from phone (e.g. +55 11 99999-1234 -> 5511999991234).
    This will be used as human-friendly document id for clients."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits if digits else None


def clean_firestore_dict(data: dict):
    """Deeply convert Firestore custom types (like Timestamps) to standard Python types."""
    if not data:
        return data
    new_data = dict(data)
    for key, value in new_data.items():
        # Handle Firestore Timestamps and other datetime-like objects
        if hasattr(value, 'to_datetime'):
            new_data[key] = value.to_datetime()
        # Recursively handle nested dicts
        elif isinstance(value, dict):
            new_data[key] = clean_firestore_dict(value)
        # Handle lists of dicts
        elif isinstance(value, list):
            new_data[key] = [clean_firestore_dict(i) if isinstance(i, dict) else i for i in value]
    return new_data


class _CollectionWrapper:
    def __init__(self, collection_name: str):
        if _firestore_client is None:
            raise RuntimeError('Firestore client not initialized. Configure Firebase credentials.')
        self.col = _firestore_client.collection(collection_name)

    async def find_one(self, filter: dict):
        return await asyncio.to_thread(self._find_one_sync, filter)

    def _find_one_sync(self, filter: dict):
        # If no filter provided, return the first document in the collection
        if not filter:
            docs = list(self.col.limit(1).stream())
            return docs[0].to_dict() if docs else None
        if 'id' in filter:
            doc = self.col.document(filter['id']).get()
            return doc.to_dict() if doc.exists else None
        key, val = next(iter(filter.items()))
        docs = list(self.col.where(key, '==', val).limit(1).stream())
        return docs[0].to_dict() if docs else None

    async def insert_one(self, doc: dict):
        return await asyncio.to_thread(self._insert_one_sync, doc)

    def _insert_one_sync(self, doc: dict):
        doc_copy = dict(doc)
        doc_id = doc_copy.get('id')
        if doc_id:
            self.col.document(doc_id).set(doc_copy)
            return {'inserted_id': doc_id}
        else:
            doc_ref = self.col.document()
            doc_copy['id'] = doc_ref.id
            doc_ref.set(doc_copy)
            return {'inserted_id': doc_copy['id']}

    async def update_one(self, filter: dict, update: dict):
        return await asyncio.to_thread(self._update_one_sync, filter, update)

    def _update_one_sync(self, filter: dict, update: dict):
        if not filter:
            return {'matched_count': 0}
        if 'id' in filter:
            doc_ref = self.col.document(filter['id'])
            doc = doc_ref.get()
            if not doc.exists:
                return {'matched_count': 0}
            if '$set' in update:
                doc_ref.update(update['$set'])
            else:
                doc_ref.update(update)
            return {'matched_count': 1}
        else:
            key, val = next(iter(filter.items()))
            docs = list(self.col.where(key, '==', val).limit(1).stream())
            if not docs:
                return {'matched_count': 0}
            doc_ref = self.col.document(docs[0].id)
            if '$set' in update:
                doc_ref.update(update['$set'])
            else:
                doc_ref.update(update)
            return {'matched_count': 1}

    async def delete_one(self, filter: dict):
        return await asyncio.to_thread(self._delete_one_sync, filter)

    def _delete_one_sync(self, filter: dict):
        if 'id' in filter:
            doc_ref = self.col.document(filter['id'])
            doc = doc_ref.get()
            if not doc.exists:
                return {'deleted_count': 0}
            doc_ref.delete()
            return {'deleted_count': 1}
        else:
            key, val = next(iter(filter.items()))
            docs = list(self.col.where(key, '==', val).limit(1).stream())
            if not docs:
                return {'deleted_count': 0}
            self.col.document(docs[0].id).delete()
            return {'deleted_count': 1}

    async def count_documents(self, filter: dict):
        return await asyncio.to_thread(self._count_documents_sync, filter)

    def _count_documents_sync(self, filter: dict):
        if not filter:
            docs = list(self.col.stream())
            return len(docs)
        key, val = next(iter(filter.items()))
        docs = list(self.col.where(key, '==', val).stream())
        return len(docs)

    def find(self, filter: dict = None):
        wrapper = self
        class _Cursor:
            def __init__(self, w, filter):
                self.w = w
                self.filter = filter or {}
                self._sort = None
                self._limit = None
            def sort(self, key, direction):
                self._sort = (key, direction)
                return self
            def limit(self, n):
                self._limit = n
                return self
            async def to_list(self, n=1000):
                return await asyncio.to_thread(self._to_list_sync, n)
            def _to_list_sync(self, n):
                if not self.filter:
                    docs = list(wrapper.col.stream())
                else:
                    key, val = next(iter(self.filter.items()))
                    docs = list(wrapper.col.where(key, '==', val).stream())
                results = [d.to_dict() for d in docs]
                if self._sort:
                    key, direction = self._sort
                    reverse = True if direction < 0 else False
                    results.sort(key=lambda x: x.get(key) or 0, reverse=reverse)
                if self._limit:
                    results = results[:self._limit]
                if n:
                    return results[:n]
                return results
        return _Cursor(wrapper, filter)


# Cria o objeto db com as coleções usadas no projeto
db = None
if _firestore_client is not None:
    db = type('DB', (), {})()
    db.users = _CollectionWrapper('users')
    db.clients = _CollectionWrapper('clients')
    db.messages = _CollectionWrapper('messages')
    db.whatsapp_config = _CollectionWrapper('whatsapp_config')

# Cria a aplicação principal sem prefixo
app = FastAPI()

# Configuração de CORS para permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas as origens em desenvolvimento
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Cria um router com o prefixo /api
api_router = APIRouter(prefix="/api")

# Segurança e autenticação
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('SECRET_KEY não definido. Configure SECRET_KEY no arquivo .env')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- AUXILIARES E AUTENTICAÇÃO ---
pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)

def verify_password(plain_password, hashed_password):
    """Verifica se a senha coincide com o hash (BCrypt ou SHA256)"""
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        try:
            return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
        except Exception:
            return False

def get_password_hash(password):
    """Gera hash de senha usando BCrypt"""
    return pwd_context.hash(password)


# --- MODELOS DE DADOS (SCHEMAS) ---
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    full_name: Optional[str] = None
    role: str  # "admin" ou "agent"
    status: str = "offline"  # "online", "busy", "paused", "offline"
    is_active: bool = True  # Para controle de acesso sem exclusão
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WhatsAppConfig(BaseModel):
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

class Client(BaseModel):
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

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    sender_type: str  # "client", "bot", "agent"
    sender_id: Optional[str] = None  # ID do agente se sender_type for "agent"
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

# --- HELPERS PARA FIRESTORE E CRM ---
async def _get_messages_subcollection(client_id: str):
    """Lê as mensagens da sub-coleção clients/{client_id}/messages no Firestore."""
    if _firestore_client is None:
        return []
    def _read():
        col = _firestore_client.collection('clients').document(client_id).collection('messages')
        try:
            # Tenta ordenar por data
            docs = list(col.order_by('timestamp').stream())
        except Exception:
            # Fallback se falhar ordenação (ex: campo faltando em algum doc)
            docs = list(col.stream())
        
        results = []
        for d in docs:
            msg_data = d.to_dict()
            if msg_data:
                # Garante que o ID do documento seja o ID da mensagem se não existir no corpo
                if 'id' not in msg_data:
                    msg_data['id'] = d.id
                results.append(clean_firestore_dict(msg_data))
        return results
    return await asyncio.to_thread(_read)

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
    # Quando auto_error=False, o objeto credentials pode ser None. Tratar isso como 401.
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar as credenciais",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Valida o token ID do Firebase vindo do frontend
        decoded_token = await asyncio.to_thread(auth.verify_id_token, credentials.credentials)
        email = decoded_token.get("email")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token do Firebase não contém email",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except Exception as e:
        logging.error(f"Erro na validação do token Firebase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar as credenciais do Firebase",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Busca o usuário no Firestore pelo e-mail (agora o identificador principal vindo do Firebase Auth)
    user = await db.users.find_one({"email": email})
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado no sistema. Entre em contato com o administrador.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_obj = User(**user)
    
    # Verifica se o usuário está ativo
    if not user_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sua conta está desativada. Entre em contato com o administrador."
        )
        
    return user_obj

# --- ROTAS DE AUTENTICAÇÃO ---
@api_router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate, admin_user: User = Depends(admin_required)):
    """Rota de registro protegida. Apenas admins podem registrar novos usuários."""
    return await create_user_admin(user_data, admin_user)

@api_router.post("/auth/login", deprecated=True)
async def login_user():
    """Rota desativada em favor do Firebase Auth."""
    raise HTTPException(
        status_code=410,
        detail="Esta rota de login foi desativada. Use o fluxo de autenticação via Firebase no frontend."
    )

@api_router.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

@api_router.put("/profile/change-password", deprecated=True)
async def change_password():
    """Rota desativada em favor do Firebase Auth."""
    raise HTTPException(
        status_code=410,
        detail="A alteração de senha deve ser feita via SDK do Firebase no frontend para sua segurança."
    )

# --- ROTAS ADMINISTRATIVAS ---
async def admin_required(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso de administrador necessário"
        )
    return current_user

@api_router.get("/admin/users", response_model=List[User])
async def get_all_users(admin_user: User = Depends(admin_required)):
    users = await db.users.find().to_list(1000)
    return [User(**user) for user in users]


@api_router.post("/admin/users", response_model=User)
async def create_user_admin(user_data: UserCreate, admin_user: User = Depends(admin_required)):
    """Cria um novo usuário (apenas para admins). Sincroniza com Firebase Auth."""
    # Valida se já existe usuário com mesmo e-mail (usado no Firebase login)
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    # 1. Cria no Firebase Auth primeiro para garantir credenciais
    try:
        fb_user = await asyncio.to_thread(
            auth.create_user,
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.full_name
        )
    except Exception as e:
        logging.error(f"Erro ao criar usuário no Firebase: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Erro no Firebase: {str(e)}")

    # 2. Cria no banco de dados local (Firestore) para permissões e metadados
    new_user = User(
        id=fb_user.uid, # Usa o UID do Firebase como ID local
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        role=user_data.role or "agent",
        is_active=True
    )

    user_dict = new_user.dict()
    # Não salvamos a senha localmente por segurança, o Firebase faz isso
    await db.users.insert_one(user_dict)

    return new_user

@api_router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, admin_user: User = Depends(admin_required)):
    # Impede que o administrador exclua a si mesmo
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=400,
            detail="Não é possível excluir sua própria conta"
        )
    
    # 1. Remove do Firebase Auth
    try:
        await asyncio.to_thread(auth.delete_user, user_id)
    except Exception as e:
        logging.warning(f"Erro ao deletar do Firebase (pode não existir): {str(e)}")

    # 2. Remove do banco local
    result = await db.users.delete_one({"id": user_id})
    if result.get('deleted_count') == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado localmente")
    
    return {"success": True, "message": "Usuário excluído com sucesso"}

@api_router.get("/admin/whatsapp-config", response_model=WhatsAppConfig)
async def get_whatsapp_config(admin_user: User = Depends(admin_required)):
    config = await db.whatsapp_config.find_one({})
    if not config:
        # Cria configuração padrão se nenhuma existir
        default_config = WhatsAppConfig()
        await db.whatsapp_config.insert_one(default_config.dict())
        return default_config
    return WhatsAppConfig(**config)

@api_router.put("/admin/whatsapp-config", response_model=WhatsAppConfig)
async def update_whatsapp_config(config_update: WhatsAppConfigUpdate, admin_user: User = Depends(admin_required)):
    # Obtém configuração existente ou cria uma nova
    existing_config = await db.whatsapp_config.find_one({})
    if not existing_config:
        new_config = WhatsAppConfig()
        config_dict = new_config.dict()
    # Atualiza com os valores fornecidos
        for key, value in config_update.dict(exclude_unset=True).items():
            if value is not None:
                config_dict[key] = value
        config_dict["updated_at"] = datetime.now(timezone.utc)
        await db.whatsapp_config.insert_one(config_dict)
        return WhatsAppConfig(**config_dict)
    
    # Atualiza a configuração existente
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
    """Testa a conexão com a API do WhatsApp. Atualmente retorna mock — implementar chamada real quando token estiver pronto."""
    config = await db.whatsapp_config.find_one({})
    if not config or not config.get("access_token") or not config.get("phone_number_id"):
        raise HTTPException(
            status_code=400,
            detail="Configuração do WhatsApp incompleta. Configure Access Token e Phone Number ID."
        )
    # TODO: substituir por chamada real à API do WhatsApp
    return {"success": True, "message": "Teste de conexão bem-sucedido (mock)"}


@api_router.post('/admin/whatsapp-obtain-app-token')
async def obtain_whatsapp_app_token(admin_user: User = Depends(admin_required)):
    """Obtém um app access token via client_id/client_secret (grant_type=client_credentials) e atualiza access_token na configuração."""
    config = await db.whatsapp_config.find_one({})
    if not config or not config.get('client_id') or not config.get('client_secret'):
        raise HTTPException(status_code=400, detail='client_id e client_secret não configurados')

    client_id = config.get('client_id')
    client_secret = config.get('client_secret')

    # Faz requisição ao Graph API para obter token de aplicativo
    token_url = 'https://graph.facebook.com/oauth/access_token'
    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }

    try:
        resp = requests.get(token_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Falha ao obter token do Graph API: {e}')

    # Atualiza access_token na config (opcional: salve só temporariamente)
    access_token = data.get('access_token')
    if not access_token:
        raise HTTPException(status_code=500, detail=f'Resposta inesperada do Graph API: {data}')

    await db.whatsapp_config.update_one({}, {'$set': {'access_token': access_token, 'updated_at': datetime.now(timezone.utc)}})

    return {'success': True, 'access_token': access_token, 'raw': data}


@api_router.get("/admin/agents-performance", response_model=List[AgentPerformance])
async def get_agents_performance(admin_user: User = Depends(admin_required)):
    """Get performance metrics for all agents"""
    agents = await db.users.find({"role": "agent"}).to_list(1000)
    performance_list = []
    
    for agent in agents:
        agent_id = agent["id"]
        
    # Conta o total de conversas atendidas por este agente
        total_conversations = await db.clients.count_documents({"assigned_agent": agent_id})
        
    # Conta as conversas finalizadas hoje
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        conversations_today = await db.clients.count_documents({
            "assigned_agent": agent_id,
            "status": "finished",
            "service_finished_at": {"$gte": today_start}
        })
        
    # Calcula o tempo médio de atendimento
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
    # Obtém conversas finalizadas nos últimos 30 dias
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    finished_conversations = await db.clients.find({
        "status": "finished",
        "service_finished_at": {"$gte": thirty_days_ago},
        "assigned_agent": {"$exists": True}
    }).to_list(1000)
    
    metrics_list = []
    for conv in finished_conversations:
    # Obtém o nome do agente
        agent = await db.users.find_one({"id": conv["assigned_agent"]})
        agent_name = agent["username"] if agent else "Desconhecido"
        
    # Calcula a duração
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

# Rotas de status do agente
@api_router.put("/agent/status")
async def update_agent_status(status_data: AgentStatus, current_user: User = Depends(get_current_user)):
    """Update agent status (online, busy, paused, offline)"""
    if current_user.id != status_data.agent_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Só é possível atualizar seu próprio status")
    
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
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    # Verifica se o usuário está atribuído a este cliente ou se é admin
    if client.get("assigned_agent") != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Não autorizado a finalizar este atendimento")
    
    update_data = {
        "status": "finished",
        "service_finished_at": datetime.now(timezone.utc)
    }
    
    # Define service_started_at se não estiver definido (fallback)
    if not client.get("service_started_at"):
        update_data["service_started_at"] = client["created_at"]
    
    await db.clients.update_one(
        {"id": client_id},
        {"$set": update_data}
    )
    
    # Atualiza o status do agente para online (disponível para novas conversas)
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"status": "online", "last_activity": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "message": "Atendimento finalizado com sucesso"}

@api_router.put("/clients/{client_id}/accept-service")
async def accept_service(client_id: str, current_user: User = Depends(get_current_user)):
    """Accept service for a client"""
    client = await db.clients.find_one({"id": client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # Não bloquear por status do agente aqui — permitimos que o agente aceite e
    # confiamos na transação do Firestore para prevenir atribuições concorrentes.
    user = await db.users.find_one({"id": current_user.id})

    # Tentar realizar a atribuição de forma atômica usando transação do Firestore
    if _firestore_client is not None:
        def _txn_accept():
            doc_ref = _firestore_client.collection('clients').document(client_id)
            transaction = _firestore_client.transaction()

            @firestore.transactional
            def _trans_logic(txn, dr):
                snap = dr.get(transaction=txn)
                if not snap.exists:
                    return {'ok': False, 'reason': 'not_found'}
                current_assigned = snap.get('assigned_agent')
                if current_assigned:
                    return {'ok': False, 'reason': 'already_assigned', 'current_agent': current_assigned}
                update_data = {
                    'status': 'human',
                    'assigned_agent': current_user.id,
                    'service_started_at': datetime.now(timezone.utc)
                }
                txn.update(dr, update_data)
                return {'ok': True}

            return _trans_logic(transaction, doc_ref)

        result = await asyncio.to_thread(_txn_accept)
        if not result.get('ok'):
            if result.get('reason') == 'not_found':
                raise HTTPException(status_code=404, detail='Cliente não encontrado')
            else:
                # outro agente já assumiu
                current_ag = result.get('current_agent', 'unknown')
                raise HTTPException(status_code=409, detail=f'Atendimento já atribuído ao agente {current_ag}')
        else:
            # broadcast event to connected frontends
            try:
                agent_name = current_user.full_name if getattr(current_user, 'full_name', None) else None
                await ws_manager.broadcast({
                    'type': 'client_assigned',
                    'client_id': client_id,
                    'assigned_agent': current_user.id,
                    'agent_name': agent_name,
                    'status': 'human'
                })
            except Exception:
                pass
    else:
        # fallback sem transação: verifica novamente e atualiza
        latest = await db.clients.find_one({"id": client_id})
        if latest.get('assigned_agent'):
            raise HTTPException(status_code=409, detail='Atendimento já atribuído a outro agente')
        update_data = {
            "status": "human",
            "assigned_agent": current_user.id,
            "service_started_at": datetime.now(timezone.utc)
        }
        await db.clients.update_one({"id": client_id}, {"$set": update_data})

    # Atualiza o status do agente para ocupado
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"status": "busy", "last_activity": datetime.now(timezone.utc)}}
    )

    return {"success": True, "message": "Atendimento aceito com sucesso"}

# Rotas de perfil
@api_router.put("/profile/update", response_model=User)
async def update_profile(profile_data: UserUpdate, current_user: User = Depends(get_current_user)):
    """Update current user profile"""
    update_data = {k: v for k, v in profile_data.dict().items() if v is not None}
    
    # Verifica se o nome de usuário é único (se estiver sendo atualizado)
    if "username" in update_data:
        existing_user = await db.users.find_one({
            "username": update_data["username"],
            "id": {"$ne": current_user.id}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Nome de usuário já cadastrado")
    
    # Verifica se o email é único (se estiver sendo atualizado)
    if "email" in update_data:
        existing_user = await db.users.find_one({
            "email": update_data["email"],
            "id": {"$ne": current_user.id}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Email já cadastrado")
    
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
        raise HTTPException(status_code=400, detail="A senha atual está incorreta")
    
    new_hashed_password = get_password_hash(password_data.new_password)
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"password": new_hashed_password}}
    )
    
    return {"success": True, "message": "Password changed successfully"}

@api_router.put("/admin/users/{user_id}", response_model=User)
async def update_user(user_id: str, user_data: UserUpdate, admin_user: User = Depends(admin_required)):
    """Update user by admin"""
    # Evita que o admin atualize a si mesmo por este endpoint
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Use profile update endpoint for your own data")
    
    update_data = {k: v for k, v in user_data.dict().items() if v is not None}
    
    # Verifica se o nome de usuário é único (se estiver sendo atualizado)
    if "username" in update_data:
        existing_user = await db.users.find_one({
            "username": update_data["username"],
            "id": {"$ne": user_id}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Nome de usuário já cadastrado")
    
    # Verifica se o email é único (se estiver sendo atualizado)
    if "email" in update_data:
        existing_user = await db.users.find_one({
            "email": update_data["email"],
            "id": {"$ne": user_id}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    if result.get('matched_count') == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    updated_user = await db.users.find_one({"id": user_id})
    return User(**updated_user)


@api_router.post('/admin/assign-client/{client_id}')
async def admin_assign_client(client_id: str, assign: AssignClientRequest, admin_user: User = Depends(admin_required)):
    """Assign a client to a specific agent if the client has no assigned agent yet."""
    client = await db.clients.find_one({"id": client_id})
    if not client:
        raise HTTPException(status_code=404, detail='Cliente não encontrado')

    if client.get('assigned_agent'):
        raise HTTPException(status_code=400, detail='Cliente já possui agente atribuído')

    # Verify agent exists
    agent = await db.users.find_one({"id": assign.agent_id})
    if not agent or agent.get('role') != 'agent':
        raise HTTPException(status_code=404, detail='Agente não encontrado')

    # Assign
    await db.clients.update_one({"id": client_id}, {"$set": {"assigned_agent": assign.agent_id, "status": "human"}})

    # Update agent status to busy
    await db.users.update_one({"id": assign.agent_id}, {"$set": {"status": "busy", "last_activity": datetime.now(timezone.utc)}})

    # broadcast assignment
    try:
        agent_user = await db.users.find_one({'id': assign.agent_id})
        agent_name = agent_user.get('full_name') if agent_user else None
        await ws_manager.broadcast({
            'type': 'client_assigned',
            'client_id': client_id,
            'assigned_agent': assign.agent_id,
            'agent_name': agent_name,
            'status': 'human'
        })
    except Exception:
        pass

    return {"success": True, "message": f"Cliente {client_id} atribuído ao agente {assign.agent_id}"}

# Rotas de cliente
@api_router.get("/clients", response_model=List[Client])
async def get_clients(current_user: User = Depends(get_current_user)):
    clients = await db.clients.find().to_list(1000)
    return [Client(**client) for client in clients]

@api_router.post("/clients", response_model=Client)
async def create_client(client_data: ClientCreate, current_user: User = Depends(get_current_user)):
    # Verifica se o cliente já existe
    existing_client = await db.clients.find_one({"phone_number": client_data.phone_number})
    if existing_client:
        raise HTTPException(
            status_code=400,
            detail="Client with this phone number already exists"
        )
    
    client = Client(**client_data.dict())
    # use normalized phone as document id if available
    phone_norm = normalize_phone(client.phone_number)
    client_dict = client.dict()
    # Garantir que novo cliente comece como BOT e sem agente atribuído
    client_dict['status'] = client_dict.get('status', 'bot')
    client_dict['assigned_agent'] = None
    client_dict['agent_name'] = None
    client_dict['display_name'] = client_dict.get('name') or client_dict.get('phone_number')
    client_dict['short_id'] = (client_dict.get('id') or '')[:8]
    client_dict['phone_normalized'] = phone_norm
    client_dict['label'] = f"{client.phone_number} — {client_dict['display_name']}"

    if phone_norm:
        # set id to normalized phone
        client_dict['id'] = phone_norm
        # write directly to Firestore using low-level client to preserve id
        await asyncio.to_thread(lambda: _firestore_client.collection('clients').document(phone_norm).set(client_dict))
    else:
        await db.clients.insert_one(client_dict)

    return Client(**client_dict)

@api_router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, client_data: ClientUpdate, current_user: User = Depends(get_current_user)):
    update_dict = client_data.dict(exclude_unset=True)
    update_data = {k: v for k, v in update_dict.items() if v is not None}
    
    # Se mudar o nome, sincroniza display_name e label
    if "name" in update_data:
        new_name = update_data["name"]
        update_data["display_name"] = new_name
        
        # Tenta pegar o telefone para montar o label
        curr = await db.clients.find_one({"id": client_id})
        if curr:
            phone = curr.get("phone_number") or curr.get("phone_normalized") or client_id
            update_data["label"] = f"{phone} — {new_name}"

    result = await db.clients.update_one(
        {"id": client_id},
        {"$set": update_data}
    )
    
    if result.get('matched_count') == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    
    updated_client = await db.clients.find_one({"id": client_id})
    return Client(**updated_client)

# Rotas de mensagens
@api_router.get("/clients/{client_id}/messages", response_model=List[Message])
async def get_client_messages(client_id: str, current_user: User = Depends(get_current_user)):
    # 1. Lê mensagens da sub-coleção (novo padrão) - já vem limpas de _get_messages_subcollection
    msgs_sub = await _get_messages_subcollection(client_id)
    
    # 2. Lê mensagens da coleção top-level (padrão antigo ou fallback)
    msgs_top_raw = await db.messages.find({"client_id": client_id}).sort("timestamp", 1).to_list(1000)
    msgs_top = [clean_firestore_dict(m) for m in msgs_top_raw]
    
    # Merge e deduplicação por ID
    merged_dict = {}
    
    # Adiciona top-level primeiro
    for m in msgs_top:
        merged_dict[m["id"]] = Message(**m)
        
    # Adiciona sub-coleção (sobrescrevendo se houver mesmo ID)
    for m in msgs_sub:
        merged_dict[m["id"]] = Message(**m)
        
    # Converte de volta para lista e ordena por timestamp
    all_messages = list(merged_dict.values())
    all_messages.sort(key=lambda x: x.timestamp)
    
    return all_messages

@api_router.post("/messages", response_model=Message)
async def create_message(message_data: MessageCreate, current_user: User = Depends(get_current_user)):
    message = Message(**message_data.dict())

    # Determine where to store message: subcollection under client if client exists
    client_id = message_data.client_id
    client_doc = None
    if client_id and _firestore_client is not None:
        try:
            client_doc = _firestore_client.collection('clients').document(client_id).get()
        except Exception:
            client_doc = None

    if client_doc and client_doc.exists:
        # write message under clients/{client_id}/messages
        def _write_msg():
            col = _firestore_client.collection('clients').document(client_id).collection('messages')
            doc_ref = col.document(message.id)
            doc_ref.set(message.dict())
        await asyncio.to_thread(_write_msg)
    else:
        # fallback to top-level messages collection
        await db.messages.insert_one(message.dict())

    # Atualiza a última interação do cliente (se existir)
    try:
        await db.clients.update_one(
            {"id": client_id},
            {"$set": {"last_interaction": message.timestamp}}
        )
    except Exception:
        pass

    return message

@api_router.get("/conversations", response_model=List[Conversation])
async def get_conversations(current_user: User = Depends(get_current_user)):
    raw_clients = await db.clients.find().sort("last_interaction", -1).to_list(1000)
    
    # Agrupa clientes por número de telefone normalizado para evitar duplicatas na UI
    deduplicated_clients = {}
    for c_data in raw_clients:
        phone = c_data.get("phone_number")
        phone_norm = normalize_phone(phone) or c_data.get("id")
        
        # Se já vimos esse telefone, decide qual manter
        if phone_norm in deduplicated_clients:
            existing = deduplicated_clients[phone_norm]
            # Prioriza o que estiver em atendimento 'human'
            if existing.get("status") != "human" and c_data.get("status") == "human":
                deduplicated_clients[phone_norm] = c_data
            # Se ambos são iguais no status, ficamos com o que já estava (que é mais recente pelo sort)
            continue
        else:
            deduplicated_clients[phone_norm] = c_data
            
    conversations = []
    # Converte e ordena novamente por interação
    clients_to_show = sorted(deduplicated_clients.values(), key=lambda x: x.get("last_interaction") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    
    for client_data in clients_to_show:
        # Obtém informações do agente se atribuído
        agent_name = None
        if client_data.get("assigned_agent"):
            agent = await db.users.find_one({"id": client_data["assigned_agent"]})
            if agent:
                agent_name = agent.get("full_name") or agent.get("username")
        
        client = Client(**client_data)
        # Adiciona agent_name aos dados do cliente
        client_dict = client.dict()
        client_dict["agent_name"] = agent_name

        # Lê a última mensagem da sub-coleção (fonte de verdade)
        try:
            last_msgs = await _get_messages_subcollection(client.id)
            if last_msgs:
                # pega apenas a última (já limpa pelo _get_messages_subcollection)
                messages_list = [Message(**last_msgs[-1])]
            else:
                # fallback: tenta a coleção top-level legada
                msgs_fallback = await db.messages.find({"client_id": client.id}).sort("timestamp", -1).limit(1).to_list(1)
                messages_list = [Message(**clean_firestore_dict(msg)) for msg in msgs_fallback]
        except Exception as e:
            logging.error(f"Erro ao carregar mensagens para cliente {client.id}: {e}")
            messages_list = []
        
        conversation = Conversation(
            client=Client(**client_dict),
            messages=messages_list,
            unread_count=0  # TODO: implementar lógica de não lidos
        )
        conversations.append(conversation)
    
    return conversations

# Rotas mock de integração com o WhatsApp
@api_router.post("/whatsapp/send")
async def send_whatsapp_message(message_data: MessageCreate, current_user: User = Depends(get_current_user)):
    """Envia mensagem ao cliente via WhatsApp Cloud API ou n8n."""
    # Obtém configuração do WhatsApp
    config = await db.whatsapp_config.find_one({})

    # Busca o telefone do cliente
    client = await db.clients.find_one({"id": message_data.client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    phone_number = client.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=400, detail="Cliente não possui número de telefone registrado")

    # Cria a mensagem antes do envio para ter o ID disponível
    message = Message(
        client_id=message_data.client_id,
        sender_type=message_data.sender_type,
        sender_id=message_data.sender_id,
        content=message_data.content
    )

    resp = None
    resp_json = {}

    # Se estiver configurado para usar n8n, envie para lá
    if config and config.get('use_n8n') and config.get('n8n_webhook_url'):
        n8n_payload = {
            'to': phone_number,
            'client_id': message_data.client_id,
            'client_name': client.get('name') or phone_number,
            'message_id': message.id,
            'sender_type': message_data.sender_type,
            'sender_id': message_data.sender_id,
            'content': message_data.content,
            'message_type': 'text',
            'timestamp': message.timestamp.isoformat()
        }
        try:
            resp = requests.post(config['n8n_webhook_url'], json=n8n_payload, timeout=10)
            resp_json = resp.json() if resp.content else {}
        except Exception as e:
            resp = None
            resp_json = {'error': str(e)}
    elif config and config.get("access_token") and config.get("phone_number_id"):
        # Monta payload para WhatsApp Cloud API (texto simples)
        phone_norm = re.sub(r"\D", "", phone_number)
        url = f"https://graph.facebook.com/v18.0/{config['phone_number_id']}/messages"
        headers = {
            "Authorization": f"Bearer {config['access_token']}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_norm,
            "type": "text",
            "text": {"body": message_data.content}
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp_json = resp.json() if resp.content else {}
        except Exception as e:
            resp = None
            resp_json = {"error": str(e)}
    else:
        raise HTTPException(status_code=400, detail="Nenhuma integração de envio configurada. Configure n8n ou WhatsApp Cloud API.")

    # Armazena resposta externa no documento da mensagem
    message_dict = message.dict()
    message_dict["external_response"] = resp_json if resp_json else None

    # Salva na sub-coleção clients/{client_id}/messages (consistente com leitura)
    client_id = message_data.client_id
    if _firestore_client is not None:
        def _write_agent_msg():
            col = _firestore_client.collection('clients').document(client_id).collection('messages')
            col.document(message.id).set(message_dict)
        await asyncio.to_thread(_write_agent_msg)
    else:
        await db.messages.insert_one(message_dict)

    # Atualiza a última interação do cliente
    await db.clients.update_one(
        {"id": client_id},
        {"$set": {"last_interaction": message.timestamp}}
    )

    # Notifica o frontend via WebSocket para atualização em tempo real
    try:
        msg_dict_ws = message.dict()
        msg_dict_ws['timestamp'] = message.timestamp.isoformat()
        await ws_manager.broadcast({
            'type': 'new_message',
            'client_id': client_id,
            'message': msg_dict_ws
        })
    except Exception:
        pass

    # Analisa resultado do envio
    if resp is not None and resp.status_code >= 200 and resp.status_code < 300:
        return {
            "success": True,
            "message_id": message.id,
            "whatsapp_response": resp_json
        }
    else:
        return {
            "success": False,
            "message_id": message.id,
            "error": resp_json,
            "note": "Envio via integração falhou. A mensagem foi salva localmente."
        }

@api_router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    # Lê body raw para possível verificação de assinatura
    raw_body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # Se houver client_secret configurado, verifique assinatura HMAC-SHA256
    try:
        config = await db.whatsapp_config.find_one({})
        client_secret = None
        if config:
            client_secret = config.get('client_secret')
        if client_secret:
            sig_header = request.headers.get('X-Hub-Signature-256') or request.headers.get('x-hub-signature-256')
            if not sig_header:
                raise HTTPException(status_code=403, detail='Assinatura ausente')
            # header do tipo: sha256=hexdigest
            try:
                prefix, hexdigest = sig_header.split('=')
            except Exception:
                raise HTTPException(status_code=403, detail='Formato de assinatura inválido')
            computed = hmac.new(client_secret.encode(), raw_body, digestmod='sha256').hexdigest()
            if not hmac.compare_digest(computed, hexdigest):
                raise HTTPException(status_code=403, detail='Assinatura inválida')
    except HTTPException:
        raise
    except Exception:
        # em caso de erro ao verificar assinatura, bloqueia por segurança
        raise HTTPException(status_code=403, detail='Erro na verificação de assinatura')
    """Webhook para receber mensagens do WhatsApp Cloud API ou payloads mock.

    Suporta formato real do WhatsApp Cloud: entry[] -> changes[] -> value -> messages
    """
    try:
        payload = await request.json()
        messages = []
        # Tenta detectar mensagens no formato do CRM (Sync do Bot/n8n)
        is_sync_request = False
        if isinstance(payload, dict):
            # Se for explicitamente sync do bot ou se tiver campos típicos do nosso n8n body
            # Ampliamos a detecção para aceitar campos comuns 'to' e 'content'/'text' como sync do bot
            has_sync_fields = ("to" in payload or "from" in payload) and ("content" in payload or "text" in payload)
            if payload.get("is_bot_sync") or payload.get("sender_type") == "bot" or payload.get("message_type") == "document" or has_sync_fields:
                is_sync_request = True
        
        if is_sync_request:
            phone_number = str(payload.get("to") or payload.get("from") or "")
            # suporte a 'content' ou 'text' (n8n pode usar ambos)
            content = payload.get("content") or payload.get("text") or ""
            # detecta tipo document se houver media_metadata
            m_type = payload.get("message_type") or ("text" if not payload.get("media_metadata") else "document")
            media_md = payload.get("media_metadata")

            # Permite sync se tiver telefone
            if not phone_number:
                return {"success": False, "error": "Faltam parâmetro 'to' ou 'from' para sync", "received": payload}
            
            # Se for texto, espera conteúdo. Se for mídia, aceitamos o processamento.
            if m_type == "text" and not content:
                 # Se vier vazio, pode ser um objeto de teste n8n sem os dados mapeados ainda
                 logging.warning(f"Webhook recebeu mensagem de texto sem conteúdo: {payload}")
            
            # Padroniza remetente automação (bot)
            messages.append((
                {"from": phone_number, "text": {"body": content}, "type": m_type, "media": media_md}, 
                {"is_bot": True, "message_type": m_type, "media_metadata": media_md}
            ))
        else:
            # Tenta detectar mensagens no formato do WhatsApp Cloud original
            if isinstance(payload, dict) and payload.get("entry"):
                for entry in payload.get("entry", []):
                    for change in entry.get("changes", []):
                        value = change.get("value", {})
                        # contatos
                        contacts = value.get("contacts") or []
                        if contacts:
                            contact_phone = contacts[0].get("wa_id") or contacts[0].get("phone_number")
                        # mensagens
                        msgs = value.get("messages") or []
                        for m in msgs:
                            messages.append((m, value))

            # Tenta detectar formato n8n puro com array
            elif isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict) and "messages" in item:
                        contacts = item.get("contacts") or []
                        if contacts:
                             contact_phone = contacts[0].get("wa_id") or contacts[0].get("phone_number")
                        msgs = item.get("messages") or []
                        for m in msgs:
                            messages.append((m, item))
                            
            # Tenta detectar formato n8n puro com objeto (item único)
            elif isinstance(payload, dict) and "messages" in payload:
                contacts = payload.get("contacts") or []
                if contacts:
                     contact_phone = contacts[0].get("wa_id") or contacts[0].get("phone_number")
                msgs = payload.get("messages") or []
                for m in msgs:
                    messages.append((m, payload))

            # Se não encontrou no formato acima, tenta formato simples
            if not messages and isinstance(payload, dict):
                # payload mock com campos from/to e text/content
                p_from = payload.get("from") or payload.get("to")
                p_text = payload.get("text") or payload.get("content")
                if p_from and p_text:
                    messages.append(({"text": {"body": p_text}, "from": p_from}, {}))

        # Processa cada mensagem encontrada
        created = 0
        for m, value in messages:
            # Verifica se é uma mensagem de sync do bot
            is_bot_msg = value.get("is_bot") is True
            
            # phone number
            phone_number = None
            # prioridade: contatos do value (apenas para Meta Cloud)
            if not is_bot_msg and value and value.get("contacts"):
                phone_number = value.get("contacts")[0].get("wa_id")
            # fallback para campo 'from' na mensagem
            if not phone_number:
                phone_number = m.get("from") or m.get("from_number") or m.get("wa_id")

            # extrai conteúdo e tipo de mensagem
            m_type = value.get("message_type") or m.get("type", "text")
            content = ""
            media_md = value.get("media_metadata") or None

            if media_md and not content:
                content = m.get("text", {}).get("body", "") or ""

            if m_type == "text":
                content = content or m.get("text", {}).get("body", "")
            elif m_type == "document":
                # Se ainda não temos metadados (Meta Cloud), tenta extrair do 'm'
                if not media_md:
                    doc = m.get("document", {})
                    content = doc.get("caption") or doc.get("filename") or "Documento"
                    media_md = {
                        "id": doc.get("id"),
                        "filename": doc.get("filename"),
                        "mime_type": doc.get("mime_type"),
                        "sha256": doc.get("sha256")
                    }
                else:
                    # Se já temos metadados (Sync do Bot), apenas garante o content
                    content = content or "Documento"
            elif m_type == "image":
                if not media_md:
                    img = m.get("image", {})
                    content = img.get("caption") or "Imagem"
                    media_md = {
                        "id": img.get("id"),
                        "mime_type": img.get("mime_type"),
                        "sha256": img.get("sha256")
                    }
                else:
                    content = content or "Imagem"
            elif m_type == "audio" or m_type == "voice":
                if not media_md:
                    aud = m.get("audio") or m.get("voice") or {}
                    content = "Áudio"
                    media_md = {"id": aud.get("id"), "mime_type": aud.get("mime_type")}
                else:
                    content = content or "Áudio"
            elif m_type == "video":
                if not media_md:
                    vid = m.get("video", {})
                    content = vid.get("caption") or "Vídeo"
                    media_md = {"id": vid.get("id"), "mime_type": vid.get("mime_type")}
                else:
                    content = content or "Vídeo"
            elif m_type == "sticker":
                if not media_md:
                    stk = m.get("sticker", {})
                    content = "Sticker"
                    media_md = {"id": stk.get("id"), "mime_type": stk.get("mime_type")}
                else:
                    content = content or "Sticker"
            elif m.get("text"):
                content = m.get("text", {}).get("body", "")
            else:
                # se for outro tipo e tiver body no text, usa ele
                content = str(m)

            # Normaliza e encontra/insere cliente
            phone_norm = normalize_phone(phone_number)
            if not phone_norm:
                continue
                
            # Busca agressiva para evitar duplicidade
            client = await db.clients.find_one({"id": phone_norm})
            if not client:
                # Tenta pelo campo phone_number (alguns podem estar salvos com o valor puro)
                client = await db.clients.find_one({"phone_number": phone_norm})
            if not client:
                # Tenta pelo campo phone_number original (pode conter +, espaços, etc)
                client = await db.clients.find_one({"phone_number": phone_number})
                
            if not client:
                # cria cliente usando phone_normalized como id
                display = (m.get("profile", {}).get("name") if m.get("profile") else f"Cliente {phone_number}")
                new_client = Client(phone_number=phone_norm, name=display)
                new_client_dict = new_client.dict()
                # garantir status inicial como bot e sem agente atribuído
                new_client_dict['status'] = 'bot'
                new_client_dict['assigned_agent'] = None
                new_client_dict['agent_name'] = None
                new_client_dict['display_name'] = display
                new_client_dict['phone_normalized'] = phone_norm
                new_client_dict['short_id'] = (phone_norm or new_client_dict['id'])[:8]
                new_client_dict['label'] = f"{phone_number} — {display}"
                new_client_dict['id'] = phone_norm # Força o ID a ser o telefone normalizado
                
                await asyncio.to_thread(lambda: _firestore_client.collection('clients').document(phone_norm).set(new_client_dict))
                client_id = phone_norm
            else:
                client_id = client.get("id") or client.get("phone_normalized") or phone_norm
                # Se o cliente já existe, NÃO sobrescrevemos o documento inteiro,
                # apenas atualizamos o que for necessário depois.


            # Cria mensagem (entrada ou saída automática)
            message = Message(
                client_id=client_id,
                sender_type="bot" if is_bot_msg else "client",
                content=content,
                message_type=m_type,
                media_metadata=media_md
            )

            # Salva na sub-coleção clients/{client_id}/messages (consistente com leitura)
            if _firestore_client is not None:
                msg_dict_save = message.dict()
                # Guarda o ID externo do WhatsApp se disponível
                if m.get('id'):
                    msg_dict_save['message_id_external'] = m.get('id')
                await asyncio.to_thread(
                    lambda md=msg_dict_save, cid=client_id, mid=message.id:
                        _firestore_client.collection('clients').document(cid)
                            .collection('messages').document(mid).set(md)
                )
            else:
                await db.messages.insert_one(message.dict())

            # Atualiza a última interação do cliente
            await db.clients.update_one({"id": client_id}, {"$set": {"last_interaction": message.timestamp}})
            created += 1

            # Notifica o frontend via WebSocket — nova mensagem recebida
            try:
                msg_dict_ws = message.dict()
                msg_dict_ws['timestamp'] = message.timestamp.isoformat()
                await ws_manager.broadcast({
                    'type': 'new_message',
                    'client_id': client_id,
                    'message': msg_dict_ws
                })
            except Exception:
                pass

        return {"success": True, "created": created}
    except Exception as e:
        return {"success": False, "error": str(e)}


@api_router.get("/whatsapp/webhook")
async def whatsapp_webhook_verify(request: Request):
    """Endpoint de verificação do webhook (utilizado pela configuração do Webhook do WhatsApp/Meta).

    Aceita query params enviados pelo Meta: hub.mode, hub.challenge, hub.verify_token
    """
    # Obtém token configurado
    config = await db.whatsapp_config.find_one({})
    expected_token = config.get("webhook_verify_token") if config else None

    hub_mode = request.query_params.get('hub.mode') or request.query_params.get('mode')
    hub_challenge = request.query_params.get('hub.challenge') or request.query_params.get('challenge')
    hub_verify = request.query_params.get('hub.verify_token') or request.query_params.get('verify_token')

    if hub_mode == "subscribe" and hub_verify and hub_challenge:
        if expected_token and hub_verify == expected_token:
            return Response(content=hub_challenge, media_type="text/plain")
        else:
            raise HTTPException(status_code=403, detail="Verify token inválido")

    raise HTTPException(status_code=400, detail="Requisição de verificação inválida")


@api_router.post("/admin/whatsapp-resend/{message_id}")
async def resend_whatsapp_message(message_id: str, admin_user: User = Depends(admin_required)):
    """Reenvia uma mensagem registrada usando as credenciais configuradas do WhatsApp Cloud API.

    Atualiza o campo external_response da mensagem com o retorno da API.
    """
    # Tenta localizar a mensagem primeiro nas subcolecoes de cada cliente
    msg = None
    # tentativa 1: procurar por documento id em clients/*/messages
    if _firestore_client is not None:
        def _search():
            # consulta feita via query collection group
            try:
                q = _firestore_client.collection_group('messages').where('id', '==', message_id).limit(1).stream()
                docs = list(q)
                return docs[0].to_dict() if docs else None
            except Exception:
                return None
        msg = await asyncio.to_thread(_search)

    # fallback: top-level messages collection
    if not msg:
        msg = await db.messages.find_one({"id": message_id})
    if not msg:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")

    # Busca cliente
    client = await db.clients.find_one({"id": msg.get("client_id")})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente da mensagem não encontrado")

    phone_number = client.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=400, detail="Cliente não possui número de telefone")

    config = await db.whatsapp_config.find_one({})
    if not config or not config.get("access_token") or not config.get("phone_number_id"):
        raise HTTPException(status_code=400, detail="Configuração do WhatsApp incompleta")

    # Normaliza telefone (remove caracteres não numéricos)
    import re
    phone_norm = re.sub(r"\D", "", phone_number)

    url = f"https://graph.facebook.com/v18.0/{config['phone_number_id']}/messages"
    headers = {"Authorization": f"Bearer {config['access_token']}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": phone_norm, "type": "text", "text": {"body": msg.get("content")}}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp_json = resp.json() if resp.content else {}
    except Exception as e:
        resp_json = {"error": str(e)}

    # Atualiza mensagem com resposta externa
    await db.messages.update_one({"id": message_id}, {"$set": {"external_response": resp_json}})

    return {"success": True, "message_id": message_id, "response": resp_json}

# Inclui o router na aplicação principal
app.include_router(api_router)


# Simple WebSocket manager to broadcast events to connected clients (frontend)
class WebSocketManager:
    def __init__(self):
        # store dicts: { 'ws': WebSocket, 'user_id': str }
        self.active_connections: list[dict] = []

    async def connect(self, websocket: WebSocket, user_id: str):
        # Accept and register the connection with the authenticated user id
        await websocket.accept()
        self.active_connections.append({'ws': websocket, 'user_id': user_id})

    def disconnect(self, websocket: WebSocket):
        try:
            # remove any entries matching this websocket
            self.active_connections = [c for c in self.active_connections if c.get('ws') is not websocket]
        except Exception:
            pass

    async def broadcast(self, message: dict):
        # send to all active connections; clean up dropped ones
        for entry in list(self.active_connections):
            connection = entry.get('ws')
            try:
                await connection.send_json(message)
            except Exception:
                try:
                    self.active_connections.remove(entry)
                except Exception:
                    pass


ws_manager = WebSocketManager()


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    # Expect token as query param ?token=...
    token = None
    try:
        params = websocket.query_params
        token = params.get('token')
    except Exception:
        token = None

    if not token:
        # reject connection
        await websocket.close(code=4401)
        return

    # validate token similarly to get_current_user
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        if username is None:
            await websocket.close(code=4401)
            return
    except Exception:
        await websocket.close(code=4401)
        return

    user = await db.users.find_one({'username': username})
    if not user:
        await websocket.close(code=4401)
        return

    user_id = user.get('id')
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            # keep connection alive; expect occasional pings from client
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    # Firestore client não precisa ser fechado explicitamente.
    try:
        if firebase_app is not None:
            # não há necessidade de chamar delete_app na maioria dos cenários, mas deixamos como noop
            pass
    except Exception:
        pass

# Cria usuário admin padrão na inicialização
@app.on_event("startup")
async def create_default_admin():
    # If Firestore is not configured, skip startup DB initialization
    if db is None:
        logger.info('Firestore client not configured; skipping default admin creation')
        return

    try:
        # Verifica se usuários existem e atualiza para conter status e full_name
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
        
    # Verifica se admin existe
        admin_exists = await db.users.find_one({"username": "admin"})
        if not admin_exists:
            # Cria usuário admin
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
        
    # Verifica se agente existe
        agent_exists = await db.users.find_one({"username": "agent1"})
        if not agent_exists:
            # Cria agente de exemplo
            agent_user = User(
                username="agent1",
                email="agent1@crm.com",
                full_name="Agente Um",
                role="agent",
                status="offline"
            )
            
            agent_dict = agent_user.dict()
            agent_dict["password"] = get_password_hash("agent123")
            await db.users.insert_one(agent_dict)
            logger.info("Sample agent user created: username=agent1, password=agent123")

        # Sincroniza configuração n8n a partir das variáveis de ambiente
        env_use_n8n = os.environ.get('USE_N8N', '').lower() in ('true', '1', 'yes')
        env_n8n_url = os.environ.get('N8N_WEBHOOK_URL', '').strip()
        if env_n8n_url:
            existing_wa_config = await db.whatsapp_config.find_one({})
            n8n_update = {
                'use_n8n': env_use_n8n,
                'n8n_webhook_url': env_n8n_url,
                'updated_at': datetime.now(timezone.utc)
            }
            if existing_wa_config:
                await db.whatsapp_config.update_one(
                    {'id': existing_wa_config['id']},
                    {'$set': n8n_update}
                )
                logger.info(f"n8n config synced from env: use_n8n={env_use_n8n}, url={env_n8n_url}")
            else:
                new_wa_cfg = WhatsAppConfig(use_n8n=env_use_n8n, n8n_webhook_url=env_n8n_url)
                cfg_dict = new_wa_cfg.dict()
                cfg_dict.update(n8n_update)
                await db.whatsapp_config.insert_one(cfg_dict)
                logger.info(f"n8n config created from env: use_n8n={env_use_n8n}, url={env_n8n_url}")

    except Exception as e:
        logger.error(f"Error creating default users: {e}")