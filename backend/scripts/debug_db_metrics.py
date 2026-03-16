
import os
import asyncio
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

# Setup Firebase
cred_val = os.environ.get('FIREBASE_CREDENTIALS_JSON')
if not cred_val:
    print("Error: FIREBASE_CREDENTIALS_JSON not set")
    exit(1)

try:
    if cred_val.strip().startswith('{'):
        # É um JSON string
        cred_dict = json.loads(cred_val)
        cred = credentials.Certificate(cred_dict)
    else:
        # É um caminho de arquivo
        cred = credentials.Certificate(cred_val)
    firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    exit(1)

db = firestore.client()

async def check_db():
    with open('debug_output.txt', 'w', encoding='utf-8') as f:
        f.write("--- Verificando Coleção: users ---\n")
        users = db.collection('users').stream()
        count = 0
        for u in users:
            d = u.to_dict()
            f.write(f"User Doc ID: {u.id}, Username: {d.get('username')}, Role: {d.get('role')}, CreatedAt: {d.get('created_at')}\n")
            count += 1
        f.write(f"Total Users: {count}\n\n")

        f.write("--- Verificando Coleção: clients (finished) ---\n")
        clients = db.collection('clients').where('status', '==', 'finished').stream()
        count = 0
        for c in clients:
            d = c.to_dict()
            f.write(f"Client: {c.id}, Status: {d.get('status')}, Agent: {d.get('assigned_agent')}\n")
            count += 1
        f.write(f"Total Finished Clients: {count}\n")
    print("Debug output written to debug_output.txt")

if __name__ == "__main__":
    asyncio.run(check_db())
