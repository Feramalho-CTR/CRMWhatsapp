import os
import json
import sys
from pathlib import Path

# Adiciona o diretório backend ao path para possíveis imports
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Setup - Carrega do diretório backend
BACKEND_DIR = Path(__file__).parent.parent
load_dotenv(BACKEND_DIR / '.env')

FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')
FIREBASE_PROJECT = os.environ.get('FIREBASE_PROJECT')

print("--- Iniciando Migração de IDs de Usuários ---")

try:
    if FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS_JSON))
        firebase_admin.initialize_app(cred)
    else:
        # Tenta Application Default
        firebase_admin.initialize_app(options={'projectId': FIREBASE_PROJECT} if FIREBASE_PROJECT else None)
except Exception as e:
    print(f"Nota: Firebase já inicializado ou erro: {e}")

db = firestore.client()

def migrate_users():
    users_ref = db.collection('users')
    docs = list(users_ref.stream())
    
    print(f"Encontrados {len(docs)} documentos na coleção 'users'.")
    
    count = 0
    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        username = data.get('username')
        
        # Só migra se o ID do documento for diferente do username
        # E se o username existir
        if username and doc_id != username:
            print(f" > Migrando: '{username}' (Document ID: {doc_id} -> {username})")
            
            # Prepara os novos dados
            new_data = dict(data)
            new_data['id'] = username
            new_data['uid'] = doc_id # Preserva o UID do Firebase no campo 'uid'
            
            # 1. Cria o novo documento com o ID legível
            users_ref.document(username).set(new_data)
            
            # 2. Remove o documento antigo com ID de código
            users_ref.document(doc_id).delete()
            count += 1
        else:
            if not username:
                print(f" ! Documento {doc_id} ignorado (username ausente)")
            else:
                print(f" . Documento {doc_id} já está correto (ID == username)")
            
    print(f"\nSucesso: {count} usuários migrados para o novo padrão de ID legível.")

if __name__ == "__main__":
    migrate_users()
