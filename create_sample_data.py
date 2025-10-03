#!/usr/bin/env python3
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import uuid
import os

# MongoDB connection
mongo_url = "mongodb://localhost:27017"
client = AsyncIOMotorClient(mongo_url)
db = client["test_database"]

async def create_sample_data():
    """Cria dados de exemplo para demonstrar o sistema"""
    
    # Limpar dados existentes
    await db.clients.delete_many({})
    await db.messages.delete_many({})
    
    # Criar clientes de exemplo
    clients_data = [
        {
            "id": str(uuid.uuid4()),
            "phone_number": "+55 11 99999-1234",
            "name": "João Silva",
            "status": "human",
            "assigned_agent": "agent1",
            "last_interaction": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": str(uuid.uuid4()),
            "phone_number": "+55 21 88888-5678",
            "name": "Maria Santos",
            "status": "bot",
            "assigned_agent": None,
            "last_interaction": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": str(uuid.uuid4()),
            "phone_number": "+55 31 77777-9012",
            "name": "Pedro Costa",
            "status": "waiting",
            "assigned_agent": None,
            "last_interaction": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": str(uuid.uuid4()),
            "phone_number": "+55 41 66666-3456",
            "name": None,  # Cliente sem nome
            "status": "bot",
            "assigned_agent": None,
            "last_interaction": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        }
    ]
    
    # Inserir clientes
    await db.clients.insert_many(clients_data)
    print(f"Criados {len(clients_data)} clientes de exemplo")
    
    # Criar mensagens de exemplo
    messages_data = []
    
    # Mensagens para João Silva (conversa ativa com humano)
    joao_id = clients_data[0]["id"]
    messages_data.extend([
        {
            "id": str(uuid.uuid4()),
            "client_id": joao_id,
            "sender_type": "client",
            "sender_id": None,
            "content": "Olá! Gostaria de saber mais sobre seus produtos.",
            "timestamp": datetime.now(timezone.utc)
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": joao_id,
            "sender_type": "bot",
            "sender_id": None,
            "content": "Olá João! Ficamos felizes com seu interesse. Em que posso ajudá-lo?",
            "timestamp": datetime.now(timezone.utc)
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": joao_id,
            "sender_type": "client", 
            "sender_id": None,
            "content": "Preciso de um orçamento para software de gestão.",
            "timestamp": datetime.now(timezone.utc)
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": joao_id,
            "sender_type": "agent",
            "sender_id": "agent1",
            "content": "Perfeito! Vou te passar um orçamento personalizado. Quantos usuários vocês têm?",
            "timestamp": datetime.now(timezone.utc)
        }
    ])
    
    # Mensagens para Maria Santos (bot ativo)
    maria_id = clients_data[1]["id"]
    messages_data.extend([
        {
            "id": str(uuid.uuid4()),
            "client_id": maria_id,
            "sender_type": "client",
            "sender_id": None,
            "content": "Oi! Vocês trabalham com delivery?",
            "timestamp": datetime.now(timezone.utc)
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": maria_id,
            "sender_type": "bot",
            "sender_id": None,
            "content": "Sim! Trabalhamos com delivery em toda a região metropolitana. Gostaria de fazer um pedido?",
            "timestamp": datetime.now(timezone.utc)
        }
    ])
    
    # Mensagens para Pedro Costa (aguardando humano)
    pedro_id = clients_data[2]["id"]
    messages_data.extend([
        {
            "id": str(uuid.uuid4()),
            "client_id": pedro_id,
            "sender_type": "client",
            "sender_id": None,
            "content": "Preciso falar com um vendedor urgente!",
            "timestamp": datetime.now(timezone.utc)
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": pedro_id,
            "sender_type": "bot",
            "sender_id": None,
            "content": "Entendi que é urgente. Estou transferindo você para um de nossos consultores.",
            "timestamp": datetime.now(timezone.utc)
        }
    ])
    
    # Mensagens para cliente sem nome
    anonimo_id = clients_data[3]["id"]
    messages_data.extend([
        {
            "id": str(uuid.uuid4()),
            "client_id": anonimo_id,
            "sender_type": "client",
            "sender_id": None,
            "content": "Oi",
            "timestamp": datetime.now(timezone.utc)
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": anonimo_id,
            "sender_type": "bot",
            "sender_id": None,
            "content": "Olá! Como posso ajudá-lo hoje?",
            "timestamp": datetime.now(timezone.utc)
        }
    ])
    
    # Inserir mensagens
    await db.messages.insert_many(messages_data)
    print(f"Criadas {len(messages_data)} mensagens de exemplo")
    
    print("\n✅ Dados de exemplo criados com sucesso!")
    print("🔐 Login com: admin / admin123 ou agent1 / agent123")

if __name__ == "__main__":
    asyncio.run(create_sample_data())