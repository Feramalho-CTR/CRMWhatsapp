import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(ROOT_DIR / '.env')

# Security
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('SECRET_KEY não definido. Configure SECRET_KEY no arquivo .env')

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# CORS
ORIGINS = [
    "https://crmcebrac.netlify.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "https://crm-whatsapp-backend-production.up.railway.app"
]

# Webhook secret for n8n integration
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '').strip()

# Firebase
FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')
FIREBASE_PROJECT = os.environ.get('FIREBASE_PROJECT')

# n8n
USE_N8N = os.environ.get('USE_N8N', '').lower() in ('true', '1', 'yes')
N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL', '').strip()
