import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect
from firebase_admin import auth

from app.db.firestore_wrapper import get_db

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Simple WebSocket manager to broadcast events to connected clients (frontend)"""

    def __init__(self):
        self.active_connections: list[dict] = []

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections.append({'ws': websocket, 'user_id': user_id})

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections = [c for c in self.active_connections if c.get('ws') is not websocket]
        except Exception:
            pass

    async def broadcast(self, message: dict):
        for entry in list(self.active_connections):
            connection = entry.get('ws')
            try:
                await connection.send_json(message)
            except Exception:
                try:
                    self.active_connections.remove(entry)
                except Exception:
                    pass

# Global instance
ws_manager = WebSocketManager()

async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get('token')
    if not token:
        await websocket.close(code=4401)
        return

    try:
        decoded_token = await asyncio.to_thread(auth.verify_id_token, token)
        email = decoded_token.get("email")
        if not email:
            await websocket.close(code=4401)
            return
    except Exception as e:
        logger.error(f"Erro na validação do token WebSocket: {e}")
        await websocket.close(code=4401)
        return

    db = get_db()
    if not db:
        await websocket.close(code=4401)
        return

    user = await db.users.find_one({'email': email})
    if not user:
        logger.error(f"Usuário WebSocket ({email}) não encontrado no banco local")
        await websocket.close(code=4401)
        return

    user_id = user.get('id')
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
