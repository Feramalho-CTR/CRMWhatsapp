import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from app.auth.dependencies import get_current_user, admin_required
from app.core.firebase import firestore_client
from app.db.firestore_wrapper import get_db
from app.models.user import User, AgentPerformance
from app.models.message import Message, MessageCreate, Conversation, ServiceMetrics
from app.models.client import Client
from app.utils.helpers import clean_firestore_dict
from app.websocket import ws_manager

router = APIRouter(tags=["messages"])
db = get_db()


async def _get_messages_subcollection(client_id: str):
    """Lê as mensagens da sub-coleção clients/{client_id}/messages no Firestore."""
    if firestore_client is None:
        return []

    def _read():
        col = firestore_client.collection('clients').document(client_id).collection('messages')
        try:
            docs = list(col.order_by('timestamp').stream())
        except Exception:
            docs = list(col.stream())

        results = []
        for d in docs:
            msg_data = d.to_dict()
            if msg_data:
                if 'id' not in msg_data:
                    msg_data['id'] = d.id
                results.append(clean_firestore_dict(msg_data))
        return results

    return await asyncio.to_thread(_read)


@router.get("/clients/{client_id}/messages", response_model=List[Message])
async def get_client_messages(client_id: str, current_user: User = Depends(get_current_user)):
    # 1. Lê mensagens da sub-coleção
    msgs_sub = await _get_messages_subcollection(client_id)

    # 2. Lê mensagens da coleção top-level (padrão antigo ou fallback)
    msgs_top_raw = await db.messages.find({"client_id": client_id}).sort("timestamp", 1).to_list(1000)
    msgs_top = [clean_firestore_dict(m) for m in msgs_top_raw]

    # Merge e deduplicação por ID
    merged_dict = {}

    for m in msgs_top:
        merged_dict[m["id"]] = Message(**m)

    for m in msgs_sub:
        merged_dict[m["id"]] = Message(**m)

    all_messages = list(merged_dict.values())
    all_messages.sort(key=lambda x: x.timestamp)

    return all_messages


@router.post("/messages", response_model=Message)
async def create_message(message_data: MessageCreate, current_user: User = Depends(get_current_user)):
    message = Message(**message_data.dict())

    client_id = message_data.client_id
    client_doc = None
    if client_id and firestore_client is not None:
        try:
            client_doc = firestore_client.collection('clients').document(client_id).get()
        except Exception:
            client_doc = None

    if client_doc and client_doc.exists:
        def _write_msg():
            col = firestore_client.collection('clients').document(client_id).collection('messages')
            doc_ref = col.document(message.id)
            doc_ref.set(message.dict())
        await asyncio.to_thread(_write_msg)
    else:
        await db.messages.insert_one(message.dict())

    # Atualiza a última interação do cliente
    try:
        await db.clients.update_one(
            {"id": client_id},
            {"$set": {"last_interaction": message.timestamp}}
        )
    except Exception:
        pass

    return message


@router.get("/conversations", response_model=List[Conversation])
async def get_conversations(current_user: User = Depends(get_current_user)):
    from app.utils.helpers import normalize_phone

    raw_clients = await db.clients.find().sort("last_interaction", -1).to_list(1000)

    # Agrupa clientes por número de telefone normalizado para evitar duplicatas na UI
    deduplicated_clients = {}
    for c_data in raw_clients:
        phone = c_data.get("phone_number")
        phone_norm = normalize_phone(phone) or c_data.get("id")

        if phone_norm in deduplicated_clients:
            existing = deduplicated_clients[phone_norm]
            if existing.get("status") != "human" and c_data.get("status") == "human":
                deduplicated_clients[phone_norm] = c_data
            continue
        else:
            deduplicated_clients[phone_norm] = c_data

    conversations = []
    clients_to_show = sorted(
        deduplicated_clients.values(),
        key=lambda x: x.get("last_interaction") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )

    for client_data in clients_to_show:
        agent_name = None
        if client_data.get("assigned_agent"):
            try:
                agent = await db.users.find_one({"id": client_data["assigned_agent"]})
                if agent:
                    agent_name = agent.get("full_name") or agent.get("username")
            except Exception as e:
                logging.error(f"Erro ao buscar agente {client_data.get('assigned_agent')} para sidebar: {e}")

        client = Client(**client_data)
        client_dict = client.dict()
        client_dict["agent_name"] = agent_name

        try:
            last_msgs = await _get_messages_subcollection(client.id)
            if last_msgs:
                messages_list = [Message(**last_msgs[-1])]
            else:
                msgs_fallback = await db.messages.find({"client_id": client.id}).sort("timestamp", -1).limit(1).to_list(1)
                messages_list = [Message(**clean_firestore_dict(msg)) for msg in msgs_fallback]
        except Exception as e:
            logging.error(f"Erro ao carregar mensagens para cliente {client.id}: {e}")
            messages_list = []

        conversation = Conversation(
            client=Client(**client_dict),
            messages=messages_list,
            unread_count=0
        )
        conversations.append(conversation)

    return conversations


@router.get("/admin/agents-performance", response_model=List[AgentPerformance])
async def get_agents_performance(admin_user: User = Depends(admin_required)):
    from app.services.metrics_service import MetricsService
    return await MetricsService.get_agents_performance()


@router.get("/admin/service-metrics", response_model=List[ServiceMetrics])
async def get_service_metrics(admin_user: User = Depends(admin_required)):
    from app.services.metrics_service import MetricsService
    return await MetricsService.get_service_metrics()
