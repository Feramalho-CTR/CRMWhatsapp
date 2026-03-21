import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.firebase import firestore_client
from app.db.firestore_wrapper import get_db
from app.models.message import Message
from app.models.whatsapp import WhatsAppConfig
from app.models.client import Client
from app.utils.helpers import clean_firestore_dict, normalize_phone


db = get_db()


class WhatsAppService:
    """Serviço para operações relacionadas ao WhatsApp"""

    @staticmethod
    async def get_config() -> Optional[WhatsAppConfig]:
        """Obtém a configuração atual do WhatsApp"""
        if db is None:
            return None
        config = await db.whatsapp_config.find_one({})
        if not config:
            return None
        return WhatsAppConfig(**config)

    @staticmethod
    async def update_config(config_update: dict) -> WhatsAppConfig:
        """Atualiza a configuração do WhatsApp"""
        if db is None:
            raise RuntimeError("Database not available")

        existing_config = await db.whatsapp_config.find_one({})
        if not existing_config:
            new_config = WhatsAppConfig()
            config_dict = new_config.dict()
        else:
            config_dict = existing_config

        # Atualiza com os valores fornecidos
        for key, value in config_update.items():
            if value is not None:
                config_dict[key] = value

        config_dict["updated_at"] = datetime.now(timezone.utc)

        if not existing_config:
            await db.whatsapp_config.insert_one(config_dict)
        else:
            await db.whatsapp_config.update_one(
                {"id": existing_config["id"]},
                {"$set": config_dict}
            )

        updated_config = await db.whatsapp_config.find_one({"id": config_dict.get("id")})
        return WhatsAppConfig(**updated_config)

    @staticmethod
    async def send_message(
        client_id: str,
        content: str,
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None,
        message_type: str = "text"
    ) -> dict:
        """Envia mensagem via WhatsApp Cloud API ou n8n"""
        if db is None:
            raise RuntimeError("Database not available")

        config = await db.whatsapp_config.find_one({})
        client = await db.clients.find_one({"id": client_id})

        if not client:
            raise ValueError("Cliente não encontrado")

        phone_number = client.get("phone_number")
        if not phone_number:
            raise ValueError("Cliente não possui número de telefone registrado")

        # Cria a mensagem
        message = Message(
            client_id=client_id,
            sender_type="agent",
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            message_type=message_type
        )

        resp = None
        resp_json = {}

        # Se estiver configurado para usar n8n, envie para lá
        if config and config.get('use_n8n') and config.get('n8n_webhook_url'):
            n8n_payload = {
                'to': phone_number,
                'client_id': client_id,
                'client_name': client.get('name') or phone_number,
                'message_id': message.id,
                'sender_type': 'agent',
                'sender_id': sender_id,
                'content': content,
                'message_type': message_type,
                'timestamp': message.timestamp.isoformat()
            }
            try:
                async with httpx.AsyncClient() as client_http:
                    resp = await client_http.post(config['n8n_webhook_url'], json=n8n_payload, timeout=10)
                resp_json = resp.json() if resp.content else {}
            except Exception as e:
                resp = None
                resp_json = {'error': str(e)}

        elif config and config.get("access_token") and config.get("phone_number_id"):
            # Monta payload para WhatsApp Cloud API
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
                "text": {"body": content}
            }
            try:
                async with httpx.AsyncClient() as client_http:
                    resp = await client_http.post(url, json=payload, headers=headers, timeout=10)
                resp_json = resp.json() if resp.content else {}
            except Exception as e:
                resp = None
                resp_json = {"error": str(e)}
        else:
            raise ValueError("Nenhuma integração de envio configurada")

        # Armazena resposta externa no documento da mensagem
        message_dict = message.dict()
        message_dict["external_response"] = resp_json if resp_json else None

        # Salva na sub-coleção
        if firestore_client is not None:
            def _write_agent_msg():
                col = firestore_client.collection('clients').document(client_id).collection('messages')
                col.document(message.id).set(message_dict)
            await asyncio.to_thread(_write_agent_msg)
        else:
            await db.messages.insert_one(message_dict)

        # Atualiza a última interação do cliente
        await db.clients.update_one(
            {"id": client_id},
            {"$set": {"last_interaction": message.timestamp}}
        )

        # Analisa resultado do envio
        if resp is not None and 200 <= resp.status_code < 300:
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

    @staticmethod
    async def resend_message(message_id: str) -> dict:
        """Reenvia uma mensagem registrada"""
        if db is None:
            raise RuntimeError("Database not available")

        # Tenta localizar a mensagem
        msg = None
        if firestore_client is not None:
            def _search():
                try:
                    q = firestore_client.collection_group('messages').where('id', '==', message_id).limit(1).stream()
                    docs = list(q)
                    return docs[0].to_dict() if docs else None
                except Exception:
                    return None
            msg = await asyncio.to_thread(_search)

        if not msg:
            msg = await db.messages.find_one({"id": message_id})

        if not msg:
            raise ValueError("Mensagem não encontrada")

        client = await db.clients.find_one({"id": msg.get("client_id")})
        if not client:
            raise ValueError("Cliente da mensagem não encontrado")

        phone_number = client.get("phone_number")
        if not phone_number:
            raise ValueError("Cliente não possui número de telefone")

        config = await db.whatsapp_config.find_one({})
        if not config or not config.get("access_token") or not config.get("phone_number_id"):
            raise ValueError("Configuração do WhatsApp incompleta")

        phone_norm = re.sub(r"\D", "", phone_number)
        url = f"https://graph.facebook.com/v18.0/{config['phone_number_id']}/messages"
        headers = {"Authorization": f"Bearer {config['access_token']}", "Content-Type": "application/json"}
        payload = {"messaging_product": "whatsapp", "to": phone_norm, "type": "text", "text": {"body": msg.get("content")}}

        try:
            async with httpx.AsyncClient() as client_http:
                resp = await client_http.post(url, json=payload, headers=headers, timeout=10)
            resp_json = resp.json() if resp.content else {}
        except Exception as e:
            resp_json = {"error": str(e)}

        await db.messages.update_one({"id": message_id}, {"$set": {"external_response": resp_json}})

        return {"success": True, "message_id": message_id, "response": resp_json}

    @staticmethod
    async def obtain_app_token() -> dict:
        """Obtém um app access token via client_id/client_secret"""
        if db is None:
            raise RuntimeError("Database not available")

        config = await db.whatsapp_config.find_one({})
        if not config or not config.get('client_id') or not config.get('client_secret'):
            raise ValueError('client_id e client_secret não configurados')

        client_id = config.get('client_id')
        client_secret = config.get('client_secret')

        token_url = 'https://graph.facebook.com/oauth/access_token'
        params = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'client_credentials'
        }

        try:
            async with httpx.AsyncClient() as client_http:
                resp = await client_http.get(token_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f'Falha ao obter token do Graph API: {e}')

        access_token = data.get('access_token')
        if not access_token:
            raise RuntimeError(f'Resposta inesperada do Graph API: {data}')

        await db.whatsapp_config.update_one(
            {},
            {'$set': {'access_token': access_token, 'updated_at': datetime.now(timezone.utc)}}
        )

        return {'success': True, 'access_token': access_token, 'raw': data}
