from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from app.auth.dependencies import get_current_user, admin_required
from app.db.firestore_wrapper import get_db
from app.models.user import User
from app.models.client import Client, ClientCreate, ClientUpdate, AssignClientRequest
from app.services.client_service import ClientService

router = APIRouter(tags=["clients"])
db = get_db()


@router.get("/clients", response_model=List[Client])
async def get_clients(current_user: User = Depends(get_current_user)):
    clients = await db.clients.find().to_list(1000)
    return [Client(**client) for client in clients]


@router.post("/clients", response_model=Client)
async def create_client(client_data: ClientCreate, current_user: User = Depends(get_current_user)):
    try:
        return await ClientService.create_client(client_data.phone_number, client_data.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, client_data: ClientUpdate, current_user: User = Depends(get_current_user)):
    update_dict = client_data.dict(exclude_unset=True)
    update_data = {k: v for k, v in update_dict.items() if v is not None}

    # Busca cliente atual para validação de segurança
    current_client = await db.clients.find_one({"id": client_id})
    if not current_client:
        raise HTTPException(status_code=404, detail="Client not found")

    # RESTRIÇÃO: Agentes não podem mudar status/atribuição de conversas que não são deles
    is_admin = current_user.role == "admin"
    changing_critical = "status" in update_data or "assigned_agent" in update_data

    if not is_admin and changing_critical:
        assigned_to = current_client.get("assigned_agent")
        if assigned_to and assigned_to != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Você não tem permissão para alterar o status de uma conversa atribuída a outro atendente."
            )

    # Se mudar o nome, sincroniza display_name e label
    if "name" in update_data:
        new_name = update_data["name"]
        update_data["display_name"] = new_name
        phone = current_client.get("phone_number") or current_client.get("phone_normalized") or client_id
        update_data["label"] = f"{phone} — {new_name}"

    result = await db.clients.update_one(
        {"id": client_id},
        {"$set": update_data}
    )

    if result.get('matched_count') == 0:
        raise HTTPException(status_code=404, detail="Client not found")

    updated_client = await db.clients.find_one({"id": client_id})
    return Client(**updated_client)


@router.put("/clients/{client_id}/finish-service")
async def finish_service(client_id: str, current_user: User = Depends(get_current_user)):
    """Mark service as finished"""
    try:
        return await ClientService.finish_service(
            client_id,
            current_user.id,
            is_admin=(current_user.role == "admin")
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.put("/clients/{client_id}/accept-service")
async def accept_service(client_id: str, current_user: User = Depends(get_current_user)):
    """Accept service for a client"""
    try:
        result = await ClientService.accept_service(
            client_id,
            current_user.id,
            is_admin=(current_user.role == "admin")
        )

        # Broadcast event to connected frontends
        try:
            from app.websockets.manager import ws_manager
            await ws_manager.broadcast({
                'type': 'client_assigned',
                'client_id': client_id,
                'assigned_agent': current_user.id,
                'agent_name': current_user.full_name or current_user.username,
                'status': 'human'
            })
        except Exception:
            pass

        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post('/admin/assign-client/{client_id}')
async def admin_assign_client(client_id: str, assign: AssignClientRequest, admin_user: User = Depends(admin_required)):
    from app.services.client_service import ClientService
    return await ClientService.assign_client(client_id, assign.agent_id)
