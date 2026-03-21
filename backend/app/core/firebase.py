import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

from .config import FIREBASE_CREDENTIALS_JSON, FIREBASE_PROJECT

firebase_app = None

# Inicializa Firebase Admin / Firestore
# Suporta duas formas de configuração:
# 1) Defina GOOGLE_APPLICATION_CREDENTIALS apontando para o arquivo JSON da conta de serviço
# 2) Ou defina a variável FIREBASE_CREDENTIALS_JSON com o conteúdo JSON da chave

try:
    if FIREBASE_CREDENTIALS_JSON:
        # carrega o JSON em memória e inicializa com o dict
        cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
        firebase_app = firebase_admin.initialize_app(cred)
    else:
        # Usa Application Default Credentials (funciona quando GOOGLE_APPLICATION_CREDENTIALS está setado)
        cred = credentials.ApplicationDefault()
        firebase_app = firebase_admin.initialize_app(cred, {'projectId': FIREBASE_PROJECT} if FIREBASE_PROJECT else None)
except Exception:
    # Tenta obter app já inicializado (por exemplo em ambiente GCP)
    try:
        firebase_app = firebase_admin.get_app()
    except Exception:
        firebase_app = None

# Cliente Firestore (síncrono). Vamos fornecer um wrapper async simples.
firestore_client = firestore.client() if firebase_app is not None else None
