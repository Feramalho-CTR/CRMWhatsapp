from fastapi import WebSocket, WebSocketDisconnect


class WebSocketManager:
    """Simple WebSocket manager to broadcast events to connected clients (frontend)"""

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


# Global instance
ws_manager = WebSocketManager()
