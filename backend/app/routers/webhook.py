from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

from app.core.config import WEBHOOK_SECRET
from app.db.firestore_wrapper import get_db
from app.models.message import Message
from app.utils.helpers import normalize_phone
from app.websocket import ws_manager

router = APIRouter(tags=["webhook"])
db = get_db()


def _check_webhook_secret(request: Request):
    """Valida a chave secreta enviada pelo n8n (header ou query param)."""
    if not WEBHOOK_SECRET:
        return
    secret = (
        request.headers.get('X-Webhook-Secret')
        or request.query_params.get('secret')
        or ''
    )
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail='Webhook secret inválido')


@router.get('/api/webhook/status')
async def webhook_check_status(request: Request, phone: str = ''):
    """
    Consulta o status do atendimento de um número de telefone.
    """
    _check_webhook_secret(request)

    if not phone:
        raise HTTPException(status_code=400, detail='Parâmetro "phone" é obrigatório')

    phone_norm = normalize_phone(phone)
    if not phone_norm:
        raise HTTPException(status_code=400, detail='Número de telefone inválido')

    client = await db.clients.find_one({'id': phone_norm})
    if not client:
        client = await db.clients.find_one({'phone_number': phone_norm})
    if not client:
        client = await db.clients.find_one({'phone_number': phone})

    if not client:
        return {
            'phone': phone_norm,
            'found': False,
            'status': 'bot',
            'handled_by_human': False,
            'assigned_agent_id': None,
            'assigned_agent_name': None,
        }

    client_status = client.get('status', 'bot')
    assigned_agent_id = client.get('assigned_agent')
    agent_name = client.get('agent_name') or None

    if assigned_agent_id and not agent_name:
        try:
            agent_doc = await db.users.find_one({'id': assigned_agent_id})
            if agent_doc:
                agent_name = agent_doc.get('full_name') or agent_doc.get('username')
        except Exception:
            pass

    return {
        'phone': phone_norm,
        'found': True,
        'status': client_status,
        'handled_by_human': client_status == 'human' and bool(assigned_agent_id),
        'assigned_agent_id': assigned_agent_id,
        'assigned_agent_name': agent_name,
    }


@router.post('/api/webhook/bot-response')
async def webhook_bot_response(request: Request):
    """
    Endpoint para o n8n registrar uma resposta do bot SOMENTE se o atendimento
    ainda estiver sob controle do bot (status != 'human').
    """
    _check_webhook_secret(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail='Corpo JSON inválido')

    phone = str(body.get('phone', '')).strip()
    content = str(body.get('content', '')).strip()

    if not phone:
        raise HTTPException(status_code=400, detail='Campo "phone" é obrigatório')
    if not content:
        raise HTTPException(status_code=400, detail='Campo "content" é obrigatório')

    phone_norm = normalize_phone(phone)
    if not phone_norm:
        raise HTTPException(status_code=400, detail='Número de telefone inválido')

    client = await db.clients.find_one({'id': phone_norm})
    if not client:
        client = await db.clients.find_one({'phone_number': phone_norm})

    if client:
        client_status = client.get('status', 'bot')
        assigned_agent_id = client.get('assigned_agent')

        if client_status == 'human' and assigned_agent_id:
            agent_name = None
            try:
                agent_doc = await db.users.find_one({'id': assigned_agent_id})
                if agent_doc:
                    agent_name = agent_doc.get('full_name') or agent_doc.get('username')
            except Exception:
                pass
            return JSONResponse(
                status_code=409,
                content={
                    'saved': False,
                    'reason': 'human_in_control',
                    'agent': agent_name,
                    'message': f'Atendimento assumido por {agent_name or assigned_agent_id}. Resposta do bot ignorada.'
                }
            )

    # Registra a mensagem como sendo do bot
    client_id = phone_norm
    message = Message(client_id=client_id, sender_type='bot', content=content)

    from app.core.firebase import firestore_client
    import asyncio

    if firestore_client is not None:
        msg_dict = message.dict()
        await asyncio.to_thread(
            lambda md=msg_dict, cid=client_id, mid=message.id:
            firestore_client.collection('clients').document(cid)
                .collection('messages').document(mid).set(md)
        )
    else:
        await db.messages.insert_one(message.dict())

    await db.clients.update_one({'id': client_id}, {'$set': {'last_interaction': message.timestamp}})

    # Notifica frontend em tempo real
    try:
        msg_ws = message.dict()
        msg_ws['timestamp'] = message.timestamp.isoformat()
        await ws_manager.broadcast({'type': 'new_message', 'client_id': client_id, 'message': msg_ws})
    except Exception:
        pass

    return {'saved': True, 'message_id': message.id}
