# Setup helper para Windows PowerShell
# - cria virtualenv em .venv
# - ativa venv (exibe instruções para a sessão atual)
# - instala pip requirements do backend
# - instala dependências do frontend com yarn (ou npm se preferir)
# - copia backend/.env.example -> backend/.env e frontend/.env.example -> frontend/.env se não existirem

param(
    [switch]$SkipFrontend
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Host "Workspace root: $root"

# 1) Python venv
if (-not (Test-Path "$root\.venv")) {
    Write-Host "Criando virtualenv em .venv..."
    python -m venv "$root\.venv"
} else {
    Write-Host "Virtualenv .venv já existe."
}

Write-Host "Ative o virtualenv na sua sessão atual com:"
Write-Host "  .\\.venv\\Scripts\\Activate.ps1"

# 2) Install backend requirements (inside venv)
Write-Host "Instalando dependências Python (backend/requirements.txt) ..."
# Use python do venv para instalar
$venvPython = "$root\\.venv\\Scripts\\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r "$root\\backend\\requirements.txt"

# 3) Copy .env examples if missing
if (-not (Test-Path "$root\\backend\\.env")) {
    Copy-Item -Path "$root\\backend\\.env.example" -Destination "$root\\backend\\.env"
    Write-Host "Criado backend/.env a partir de backend/.env.example"
} else {
    Write-Host "backend/.env já existe — não foi alterado."
}

if (-not (Test-Path "$root\\frontend\\.env")) {
    Copy-Item -Path "$root\\frontend\\.env.example" -Destination "$root\\frontend\\.env"
    Write-Host "Criado frontend/.env a partir de frontend/.env.example"
} else {
    Write-Host "frontend/.env já existe — não foi alterado."
}

if (-not $SkipFrontend) {
    # 4) Frontend deps
    Write-Host "Instalando dependências do frontend... (vai usar yarn se disponível, senão npm)"
    Push-Location "$root\\frontend"
    try {
        $yarn = Get-Command yarn -ErrorAction SilentlyContinue
        if ($yarn) {
            Write-Host "yarn detectado. Executando: yarn install"
            yarn install
        } else {
            Write-Host "yarn não detectado. Usando npm install"
            npm install
        }
    } finally {
        Pop-Location
    }
}

Write-Host "Setup concluído. Próximos passos:\n - Ative o venv: .\\.venv\\Scripts\\Activate.ps1\n - Ajuste backend/.env para configurar suas credenciais do Firebase (GOOGLE_APPLICATION_CREDENTIALS ou FIREBASE_CREDENTIALS_JSON)\n - Execute o backend: python -m uvicorn backend.server:app --reload --host 0.0.0.0 --port 8000\n - No frontend: cd frontend && yarn start (ou npm run start)\n"
