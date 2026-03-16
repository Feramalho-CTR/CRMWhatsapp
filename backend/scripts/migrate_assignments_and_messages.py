import os
import json
import sys
import logging
from pathlib import Path
from datetime import datetime

# Adiciona o diretório backend ao path para possíveis imports
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Setup - Carrega do diretório backend
BACKEND_DIR = Path(__file__).parent.parent
load_dotenv(BACKEND_DIR / '.env')

FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')
FIREBASE_PROJECT = os.environ.get('FIREBASE_PROJECT')

logging.info("--- Iniciando Migração de Atribuições e Mensagens ---")

try:
    if FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS_JSON))
        firebase_admin.initialize_app(cred)
    else:
        # Tenta Application Default
        firebase_admin.initialize_app(options={'projectId': FIREBASE_PROJECT} if FIREBASE_PROJECT else None)
except Exception as e:
    logging.info(f"Nota: Firebase já inicializado ou erro: {e}")

db = firestore.client()

def migrate_assignments_and_messages():
    # 1. Criar mapa de UID -> Username e Full Name
    # O Firestore agora usa o username como Document ID, mas o UID está no campo 'uid'
    users_ref = db.collection('users')
    users_docs = users_ref.stream()
    
    uid_to_user = {}
    for doc in users_docs:
        data = doc.to_dict()
        uid = data.get('uid')
        username = data.get('username')
        full_name = data.get('full_name') or username
        
        if uid and username:
            uid_to_user[uid] = {
                'username': username,
                'full_name': full_name
            }
    
    logging.info(f"Mapeados {len(uid_to_user)} usuários do sistema.")
    if not uid_to_user:
        logging.error("Nenhum usuário com campo 'uid' encontrado. Certifique-se de que a migração anterior foi concluída.")
        return

    # 2. Migrar atribuições em 'clients'
    clients_ref = db.collection('clients')
    clients_docs = clients_ref.stream()
    client_count = 0
    
    logging.info("Migrando atribuições na coleção 'clients'...")
    for doc in clients_docs:
        data = doc.to_dict()
        agent_id = data.get('assigned_agent')
        
        # Se o agent_id for um UID (está no nosso mapa), trocamos pelo username
        if agent_id in uid_to_user:
            new_agent_id = uid_to_user[agent_id]['username']
            clients_ref.document(doc.id).update({
                'assigned_agent': new_agent_id
            })
            client_count += 1
            logging.info(f"  > Cliente {doc.id}: Atribuição alterada {agent_id} -> {new_agent_id}")

    logging.info(f"Sucesso: {client_count} clientes atualizados.")

    # 3. Migrar mensagens em subcoleções de todos os clientes
    messages_count = 0
    logging.info("Migrando mensagens em subcoleções (clients/{id}/messages)...")
    
    all_clients = clients_ref.stream()
    for client_doc in all_clients:
        msg_ref = clients_ref.document(client_doc.id).collection('messages')
        msg_docs = msg_ref.stream()
        
        for msg_doc in msg_docs:
            msg_data = msg_doc.to_dict()
            sender_id = msg_data.get('sender_id')
            sender_type = msg_data.get('sender_type')
            
            # Só migramos se for do tipo 'agent' e o ID estiver no nosso mapa
            if sender_type == 'agent' and sender_id in uid_to_user:
                new_sender_id = uid_to_user[sender_id]['username']
                new_sender_name = uid_to_user[sender_id]['full_name']
                
                msg_ref.document(msg_doc.id).update({
                    'sender_id': new_sender_id,
                    'sender_name': new_sender_name
                })
                messages_count += 1
                #logging.info(f"    > Mensagem {msg_doc.id} atualizada.")
            
            # Caso especial: Se já for o username, mas estiver faltando o sender_name, tentamos preencher
            elif sender_type == 'agent' and not msg_data.get('sender_name'):
                # Procura no mapa pelo username (caso o sender_id já seja o username)
                for u_data in uid_to_user.values():
                    if u_data['username'] == sender_id:
                        msg_ref.document(msg_doc.id).update({
                            'sender_name': u_data['full_name']
                        })
                        messages_count += 1
                        break

    logging.info(f"Sucesso: {messages_count} mensagens atualizadas.")
    logging.info("--- Migração concluída com sucesso ---")

if __name__ == "__main__":
    migrate_assignments_and_messages()
