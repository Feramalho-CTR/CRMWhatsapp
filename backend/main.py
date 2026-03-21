from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app import db
from app.core.config import ORIGINS, FIREBASE_PROJECT, USE_N8N, N8N_WEBHOOK_URL
from app.routers import api_router
from app.utils.logger import logger
from app.websockets.manager import websocket_endpoint

# Cria a aplicação FastAPI
app = FastAPI(
    title="CRM WhatsApp API",
    description="API para CRM de WhatsApp com integração Firebase",
    version="2.0.0"
)

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@app.middleware("http")
async def add_cors_header_to_errors(request: Request, call_next):
    """Garante que erros também tenham headers CORS para que o frontend veja o erro real."""
    try:
        response = await call_next(request)
        origin = request.headers.get("origin")
        if origin in ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"ERRO NÃO TRATADO NO MIDDLEWARE: {str(e)}\n{error_details}")
        content = {
            "detail": f"Erro interno do servidor: {str(e)}",
            "type": "unhandled_exception",
            "debug_info": error_details
        }
        response = JSONResponse(status_code=500, content=content)
        origin = request.headers.get("origin")
        if origin in ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

# Inclui as rotas WebSocket
app.add_api_websocket_route("/ws", websocket_endpoint)

# Inclui o router principal da API
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    logger.info("==========================================")
    logger.info("BACKEND VERSION: 2.0 - FIREBASE AUTH ACTIVE")
    logger.info(f"PROJECT ID: {FIREBASE_PROJECT}")
    logger.info("==========================================")

    if db is None:
        logger.info('Firestore client not configured; skipping default admin creation')
        return

    try:
        existing_users = await db.users.find({}).to_list(1000)
        for user in existing_users:
            update_fields = {}
            if "status" not in user:
                update_fields["status"] = "offline"
                update_fields["last_activity"] = datetime.now(timezone.utc)
            if "full_name" not in user:
                update_fields["full_name"] = user.get("username", "")

            if update_fields:
                await db.users.update_one({"id": user["id"]}, {"$set": update_fields})

        if N8N_WEBHOOK_URL:
            existing_wa_config = await db.whatsapp_config.find_one({})
            n8n_update = {'use_n8n': USE_N8N, 'n8n_webhook_url': N8N_WEBHOOK_URL, 'updated_at': datetime.now(timezone.utc)}
            if existing_wa_config:
                await db.whatsapp_config.update_one({'id': existing_wa_config['id']}, {'$set': n8n_update})
                logger.info(f"n8n config synced from env: use_n8n={USE_N8N}, url={N8N_WEBHOOK_URL}")
            else:
                from app.models.whatsapp import WhatsAppConfig
                new_wa_cfg = WhatsAppConfig(use_n8n=USE_N8N, n8n_webhook_url=N8N_WEBHOOK_URL)
                cfg_dict = new_wa_cfg.dict()
                cfg_dict.update(n8n_update)
                await db.whatsapp_config.insert_one(cfg_dict)
                logger.info(f"n8n config created from env: use_n8n={USE_N8N}, url={N8N_WEBHOOK_URL}")

    except Exception as e:
        logger.error(f"Error creating default users: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    logger.info("Shutting down application...")
