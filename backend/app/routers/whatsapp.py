import asyncio
import hmac
import json
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response, Depends

from app.auth.dependencies import get_current_user, admin_required
from app.core.firebase import firestore_client
from app.core.config import WEBHOOK_SECRET
from app.db.firestore_wrapper import get_db
from app.models.user import User
from app.models.message import MessageCreate, Message
from app.models.whatsapp import WhatsAppConfig, WhatsAppConfigUpdate
from app.models.client import Client
from app.services.whatsapp_service import WhatsAppService
from app.utils.helpers import normalize_phone, clean_firestore_dict
from app.websockets.manager import ws_manager

router = APIRouter(tags=["whatsapp"])
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


@router.post("/whatsapp/send")
async def send_whatsapp_message(message_data: MessageCreate, current_user: User = Depends(get_current_user)):
    """Envia mensagem ao cliente via WhatsApp Cloud API ou n8n."""
    try:
        result = await WhatsAppService.send_message(
            client_id=message_data.client_id,
            content=message_data.content,
            sender_id=message_data.sender_id,
            sender_name=current_user.full_name or current_user.username,
            message_type=message_data.message_type
        )

        # Notifica o frontend via WebSocket
        try:
            from app.models.message import Message
            msg = Message(**message_data.dict())
            msg_dict = msg.dict()
            msg_dict['timestamp'] = msg.timestamp.isoformat()
            await ws_manager.broadcast({
                'type': 'new_message',
                'client_id': message_data.client_id,
                'message': msg_dict
            })
        except Exception:
            pass

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """Webhook para receber mensagens do WhatsApp Cloud API ou payloads mock."""
    raw_body = await request.body()
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        try:
            form_data = await request.form()
            payload = dict(form_data)
        except Exception:
            payload = {}

    # Verificação de assinatura HMAC-SHA256
    try:
        config = await db.whatsapp_config.find_one({})
        client_secret = None
        if config:
            client_secret = config.get('client_secret')
        if client_secret:
            sig_header = request.headers.get('X-Hub-Signature-256') or request.headers.get('x-hub-signature-256')
            if not sig_header:
                raise HTTPException(status_code=403, detail='Assinatura ausente')
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
        raise HTTPException(status_code=403, detail='Erro na verificação de assinatura')

    try:
        messages = []
        is_sync_request = False

        if isinstance(payload, dict):
            has_sync_fields = ("to" in payload or "from" in payload) and ("content" in payload or "text" in payload)
            has_interactive_sync = ("to" in payload or "from" in payload) and (payload.get("type") == "interactive" or payload.get("message_type") == "interactive")

            if payload.get("is_bot_sync") or payload.get("sender_type") == "bot" or payload.get("message_type") == "document" or has_sync_fields or has_interactive_sync:
                is_sync_request = True

        if is_sync_request:
            phone_number = str(payload.get("to") or payload.get("from") or "")
            raw_content = payload.get("content") or payload.get("text")

            if payload.get("message_type"):
                m_type = payload.get("message_type")
            elif payload.get("interactive") or payload.get("type") == "interactive":
                m_type = "interactive"
            else:
                m_type = "document" if payload.get("media_metadata") else "text"

            if m_type == "interactive":
                interactive_data = payload.get("interactive") or payload
                content = json.dumps(interactive_data, ensure_ascii=False)
            else:
                content = raw_content or ""

            media_md = payload.get("media_metadata")

            if not phone_number:
                return {"success": False, "error": "Faltam parâmetro 'to' ou 'from' para sync", "received": payload}

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
                        contacts = value.get("contacts") or []
                        msgs = value.get("messages") or []
                        for m in msgs:
                            messages.append((m, value))

            elif isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict) and "messages" in item:
                        contacts = item.get("contacts") or []
                        msgs = item.get("messages") or []
                        for m in msgs:
                            messages.append((m, item))

            elif isinstance(payload, dict) and "messages" in payload:
                contacts = payload.get("contacts") or []
                msgs = payload.get("messages") or []
                for m in msgs:
                    messages.append((m, payload))

            if not messages and isinstance(payload, dict):
                p_from = payload.get("from") or payload.get("to")
                p_text = payload.get("text") or payload.get("content")
                if p_from and p_text:
                    messages.append(({"text": {"body": p_text}, "from": p_from}, {}))

        created = 0
        for m, value in messages:
            try:
                is_bot_msg = value.get("is_bot") is True
                phone_number = None

                if not is_bot_msg and value and value.get("contacts"):
                    phone_number = value.get("contacts")[0].get("wa_id")
                if not phone_number:
                    phone_number = m.get("from") or m.get("from_number") or m.get("wa_id")

                m_type = value.get("message_type") or m.get("type", "text")
                content = ""
                media_md = value.get("media_metadata") or None

                if media_md and not content:
                    content = m.get("text", {}).get("body", "") or ""

                if m_type == "text":
                    content = content or m.get("text", {}).get("body", "")
                elif m_type == "document":
                    if not media_md:
                        doc = m.get("document", {})
                        content = doc.get("caption") or doc.get("filename") or "Documento"
                        media_md = {"id": doc.get("id"), "filename": doc.get("filename"), "mime_type": doc.get("mime_type"), "sha256": doc.get("sha256")}
                    else:
                        content = content or "Documento"
                elif m_type == "image":
                    if not media_md:
                        img = m.get("image", {})
                        content = img.get("caption") or "Imagem"
                        media_md = {"id": img.get("id"), "mime_type": img.get("mime_type"), "sha256": img.get("sha256")}
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
                elif m_type == "contacts" or m.get("type") == "contacts":
                    m_type = "contacts"
                    contacts_data = m.get("contacts", [])
                    content = json.dumps(contacts_data, ensure_ascii=False)
                elif m_type == "sticker" or m.get("type") == "sticker":
                    m_type = "sticker"
                    if not media_md:
                        stk = m.get("sticker", {})
                        content = "Sticker"
                        media_md = {"id": stk.get("id"), "mime_type": stk.get("mime_type")}
                    else:
                        content = content or "Sticker"
                elif m_type == "interactive" or m.get("type") == "interactive":
                    m_type = "interactive"
                    interactive_data = m.get("interactive", {})
                    inter_type = interactive_data.get("type")
                    if inter_type == "button_reply":
                        content = interactive_data.get("button_reply", {}).get("title", "Botão Interativo")
                    elif inter_type == "list_reply":
                        content = interactive_data.get("list_reply", {}).get("title", "Lista Interativa")
                    else:
                        content = "Resposta Interativa"
                elif m.get("text"):
                    content = m.get("text", {}).get("body", "")
                else:
                    content = str(m)

                phone_norm = normalize_phone(phone_number)
                if not phone_norm:
                    continue

                client = await db.clients.find_one({"id": phone_norm})
                if not client:
                    client = await db.clients.find_one({"phone_number": phone_norm})
                if not client:
                    client = await db.clients.find_one({"phone_number": phone_number})

                if not client:
                    display = (m.get("profile", {}).get("name") if m.get("profile") else f"Cliente {phone_number}")
                    from app.models.client import Client
                    new_client = Client(phone_number=phone_norm, name=display)
                    new_client_dict = new_client.dict()
                    new_client_dict['status'] = 'bot'
                    new_client_dict['assigned_agent'] = None
                    new_client_dict['agent_name'] = None
                    new_client_dict['display_name'] = display
                    new_client_dict['phone_normalized'] = phone_norm
                    new_client_dict['short_id'] = (phone_norm or new_client_dict['id'])[:8]
                    new_client_dict['label'] = f"{phone_number} — {display}"
                    new_client_dict['id'] = phone_norm

                    await asyncio.to_thread(lambda: firestore_client.collection('clients').document(phone_norm).set(new_client_dict))
                    client_id = phone_norm
                else:
                    client_id = client.get("id") or client.get("phone_normalized") or phone_norm

                message = Message(
                    client_id=client_id,
                    sender_type="bot" if is_bot_msg else "client",
                    content=content,
                    message_type=m_type,
                    media_metadata=media_md
                )

                if firestore_client is not None:
                    msg_dict_save = message.dict()
                    if m.get('id'):
                        msg_dict_save['message_id_external'] = m.get('id')
                    # Usa timestamp formatado + os primeiros 6 caracteres do ID para evitar colisão, 
                    # assim as mensagens ficam visivelmente ordenadas por data no Firebase.
                    time_prefix = message.timestamp.strftime('%Y-%m-%d_%H-%M-%S')
                    custom_doc_id = f"{time_prefix}_{message.id[:6]}"
                    
                    await asyncio.to_thread(
                        lambda md=msg_dict_save, cid=client_id, mid=custom_doc_id:
                        firestore_client.collection('clients').document(cid).collection('messages').document(mid).set(md)
                    )
                else:
                    await db.messages.insert_one(message.dict())

                await db.clients.update_one({"id": client_id}, {"$set": {"last_interaction": message.timestamp}})
                created += 1

                # Notifica o frontend via WebSocket
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
            except Exception as e:
                logging.error(f"Erro individual ao processar mensagem do webhook: {e}", exc_info=True)
                continue

        return {"success": True, "created": created}
    except Exception as e:
        logging.error(f"Erro crítico no processamento do lote do webhook: {e}")
        return {"success": False, "error": str(e)}


@router.get("/whatsapp/webhook")
async def whatsapp_webhook_verify(request: Request):
    """Endpoint de verificação do webhook (utilizado pela configuração do Webhook do WhatsApp/Meta)."""
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


@router.post("/admin/whatsapp-resend/{message_id}")
async def resend_whatsapp_message(message_id: str, admin_user: User = Depends(admin_required)):
    """Reenvia uma mensagem registrada usando as credenciais configuradas do WhatsApp Cloud API."""
    try:
        return await WhatsAppService.resend_message(message_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/admin/whatsapp-config", response_model=WhatsAppConfig)
async def get_whatsapp_config(admin_user: User = Depends(admin_required)):
    config = await db.whatsapp_config.find_one({})
    if not config:
        default_config = WhatsAppConfig()
        await db.whatsapp_config.insert_one(default_config.dict())
        return default_config
    return WhatsAppConfig(**config)


@router.put("/admin/whatsapp-config", response_model=WhatsAppConfig)
async def update_whatsapp_config(config_update: WhatsAppConfigUpdate, admin_user: User = Depends(admin_required)):
    service = WhatsAppService()
    return await service.update_config(config_update.dict(exclude_unset=True))


@router.post("/admin/test-whatsapp")
async def test_whatsapp_connection(admin_user: User = Depends(admin_required)):
    config = await db.whatsapp_config.find_one({})
    if not config or not config.get("access_token") or not config.get("phone_number_id"):
        raise HTTPException(status_code=400, detail="Configuração do WhatsApp incompleta.")
    return {"success": True, "message": "Teste de conexão bem-sucedido"}


@router.post('/admin/whatsapp-obtain-app-token')
async def obtain_whatsapp_app_token(admin_user: User = Depends(admin_required)):
    service = WhatsAppService()
    return await service.obtain_app_token()
