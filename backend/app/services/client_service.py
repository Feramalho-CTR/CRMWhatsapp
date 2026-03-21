import asyncio
import re
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

from app.core.firebase import firestore_client
from app.db.firestore_wrapper import get_db
from app.models.client import Client
from app.models.message import Message
from app.utils.helpers import normalize_phone
from app.websockets.manager import ws_manager


db = get_db()


class ClientService:
    """Serviço para operações relacionadas a clientes"""

    @staticmethod
    async def create_client(phone_number: str, name: Optional[str] = None) -> Client:
        """Cria um novo cliente"""
        if db is None:
            raise RuntimeError("Database not available")

        # Verifica se o cliente já existe
        existing_client = await db.clients.find_one({"phone_number": phone_number})
        if existing_client:
            raise ValueError("Client with this phone number already exists")

        client = Client(phone_number=phone_number, name=name)
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
            client_dict['id'] = phone_norm
            await asyncio.to_thread(
                lambda: firestore_client.collection('clients').document(phone_norm).set(client_dict)
            )
        else:
            await db.clients.insert_one(client_dict)

        return Client(**client_dict)

    @staticmethod
    async def accept_service(client_id: str, agent_id: str, is_admin: bool = False) -> dict:
        """Aceita atendimento de um cliente"""
        if db is None:
            raise RuntimeError("Database not available")

        client = await db.clients.find_one({"id": client_id})
        if not client:
            raise ValueError("Cliente não encontrado")

        # Agentes SÓ podem aceitar um atendimento que está com o BOT
        if client.get('status') != 'bot' and not is_admin:
            status_atual = client.get('status', 'desconhecido')
            raise PermissionError(f'Agentes só podem assumir conversas que estão com o BOT. Status atual: {status_atual}.')

        # Tentar realizar a atribuição de forma atômica usando transação do Firestore
        if firestore_client is not None:
            def _txn_accept():
                from firebase_admin import firestore
                doc_ref = firestore_client.collection('clients').document(client_id)
                transaction = firestore_client.transaction()

                @firestore.transactional
                def _trans_logic(txn, dr):
                    snap = dr.get(transaction=txn)
                    if not snap.exists:
                        return {'ok': False, 'reason': 'not_found'}

                    current_status = snap.get('status')
                    current_assigned = snap.get('assigned_agent')

                    if current_status != 'bot' and not is_admin:
                        return {'ok': False, 'reason': 'not_allowed', 'current_status': current_status}

                    update_data = {
                        'status': 'human',
                        'assigned_agent': agent_id,
                        'service_started_at': datetime.now(timezone.utc)
                    }
                    txn.update(dr, update_data)
                    return {'ok': True}

                return _trans_logic(transaction, doc_ref)

            result = await asyncio.to_thread(_txn_accept)
            if not result.get('ok'):
                if result.get('reason') == 'not_found':
                    raise ValueError('Cliente não encontrado')
                else:
                    curr_st = result.get('current_status', 'unknown')
                    raise PermissionError(f'Não é permitido assumir esta conversa. Status: {curr_st}')
        else:
            # fallback sem transação
            latest = await db.clients.find_one({"id": client_id})
            if latest.get('status') != 'bot' and not is_admin:
                raise PermissionError(f"Agentes não podem assumir conversas fora do modo BOT. Status: {latest.get('status')}")

            update_data = {
                "status": "human",
                "assigned_agent": agent_id,
                "service_started_at": datetime.now(timezone.utc)
            }
            await db.clients.update_one({"id": client_id}, {"$set": update_data})

        # Atualiza o status do agente para ocupado
        await db.users.update_one(
            {"id": agent_id},
            {"$set": {"status": "busy", "last_activity": datetime.now(timezone.utc)}}
        )

        return {"success": True, "message": "Atendimento aceito com sucesso"}

    @staticmethod
    async def finish_service(client_id: str, agent_id: str, is_admin: bool = False) -> dict:
        """Finaliza atendimento de um cliente"""
        if db is None:
            raise RuntimeError("Database not available")

        client = await db.clients.find_one({"id": client_id})
        if not client:
            raise ValueError("Cliente não encontrado")

        # Verifica se o usuário está atribuído a este cliente ou se é admin
        if client.get("assigned_agent") != agent_id and not is_admin:
            raise PermissionError("Não autorizado a finalizar este atendimento")

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

        # Atualiza o status do agente para online
        await db.users.update_one(
            {"id": agent_id},
            {"$set": {"status": "online", "last_activity": datetime.now(timezone.utc)}}
        )

        return {"success": True, "message": "Atendimento finalizado com sucesso"}

    @staticmethod
    async def assign_client(client_id: str, new_agent_id: str) -> dict:
        """Admin atribui (ou reatribui) um cliente a um agente específico"""
        if db is None:
            raise RuntimeError("Database not available")

        client = await db.clients.find_one({"id": client_id})
        if not client:
            raise ValueError('Cliente não encontrado')

        # Verify target user exists and is agent or admin
        agent = await db.users.find_one({"id": new_agent_id})
        if not agent or agent.get('role') not in ('agent', 'admin'):
            raise ValueError('Agente não encontrado')

        old_agent_id = client.get('assigned_agent')

        # Assign (or reassign)
        if firestore_client is not None:
            def _write():
                firestore_client.collection('clients').document(client_id).update({
                    'assigned_agent': new_agent_id,
                    'status': 'human'
                })
            await asyncio.to_thread(_write)

        await db.clients.update_one(
            {"id": client_id},
            {"$set": {"assigned_agent": new_agent_id, "status": "human"}}
        )

        # Update new agent status to busy
        await db.users.update_one(
            {"id": new_agent_id},
            {"$set": {"status": "busy", "last_activity": datetime.now(timezone.utc)}}
        )

        # If reassigned, free old agent
        if old_agent_id and old_agent_id != new_agent_id:
            still_busy = await db.clients.find_one({"assigned_agent": old_agent_id, "status": "human"})
            if not still_busy:
                await db.users.update_one({"id": old_agent_id}, {"$set": {"status": "online"}})

        # Broadcast assignment via WebSocket
        try:
            agent_name = agent.get('full_name') or agent.get('username')
            await ws_manager.broadcast({
                'type': 'client_assigned',
                'client_id': client_id,
                'assigned_agent': new_agent_id,
                'agent_name': agent_name,
                'status': 'human'
            })
        except Exception:
            pass

        return {"success": True, "message": f"Cliente {client_id} atribuído ao agente {new_agent_id}"}
