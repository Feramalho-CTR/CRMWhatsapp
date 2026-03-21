# Routers package
from fastapi import APIRouter

api_router = APIRouter(prefix="/api")

from . import users, clients, messages, whatsapp, webhook

api_router.include_router(users.router)
api_router.include_router(clients.router)
api_router.include_router(messages.router)
api_router.include_router(whatsapp.router)
api_router.include_router(webhook.router)
