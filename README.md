# Here are your Instructions
Crm criado para integração de agente whatsapp n8n, api oficial do whatsapp

Migração do backend para Firebase/Firestore
-----------------------------------------

O backend foi modificado para usar Firestore (Firebase) em vez de MongoDB. Antes de iniciar o servidor backend, siga estes passos:

1) Instale dependências do backend (recomendo usar um virtualenv):

	pip install -r backend/requirements.txt

2) Configure credenciais do Firebase:

	- Coloque o arquivo JSON da conta de serviço do Firebase em um caminho local e defina a variável de ambiente:

	  setx GOOGLE_APPLICATION_CREDENTIALS "C:\caminho\para\service-account.json"

	- Ou defina a variável de ambiente `FIREBASE_CREDENTIALS_JSON` com o conteúdo do JSON (útil em containers/CI).

3) Opcional: defina `FIREBASE_PROJECT` no arquivo `backend/.env` se necessário.

4) Inicie o backend:

	python -m uvicorn backend.server:app --reload --host 0.0.0.0 --port 8000

Observação: algumas funcionalidades dependem de credenciais do Firebase e das variáveis adicionadas no `backend/.env`.
