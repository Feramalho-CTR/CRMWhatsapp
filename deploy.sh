#!/bin/bash
set -e

echo "=== Iniciando o Deploy Automático ==="

# Define o diretório do projeto (ajuste se a pasta na VM for diferente)
PROJECT_DIR="/home/ubuntu/novoCRM"
if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
else
    # Fallback para o diretório onde o script está localizado
    cd "$(dirname "$0")"
fi

echo "Diretório atual: $(pwd)"

echo "1. Puxando as alterações do Git..."
git pull origin main

echo "2. Reiniciando os containers com Docker Compose..."
docker compose down
docker compose up -d --build

echo "3. Status dos containers:"
docker compose ps

echo "=== Deploy finalizado com sucesso! ==="
