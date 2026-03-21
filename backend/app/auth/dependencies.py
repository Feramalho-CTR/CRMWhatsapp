import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from app.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.db.firestore_wrapper import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)

db = get_db()


def verify_password(plain_password, hashed_password):
    """Verifica se a senha coincide com o hash (BCrypt ou SHA256)"""
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        try:
            return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
        except Exception:
            return False


def get_password_hash(password):
    """Gera hash de senha usando BCrypt"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    logging.info(f"--- Autenticando requisição para {request.url.path} [V2.1] ---")
    # Quando auto_error=False, o objeto credentials pode ser None. Tratar isso como 401.
    if credentials is None:
        logging.warning(f"Requisição sem header de autorização para {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header de autorização (Bearer Token) ausente ou malformado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Valida o token ID do Firebase vindo do frontend
        decoded_token = await asyncio.to_thread(auth.verify_id_token, credentials.credentials)
        email = decoded_token.get("email")

        if not email:
            logging.error("Token do Firebase validado, mas não contém email")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token do Firebase não contém email",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except Exception as e:
        logging.error(f"Erro na validação do token Firebase: {str(e)}")
        # Incluímos o erro detalhado para ajudar no debug (pode ser removido depois)
        detail_msg = f"Falha na validação do token: {str(e)} [V2.1]"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail_msg,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível"
        )

    # Busca o usuário no Firestore pelo e-mail
    user = await db.users.find_one({"email": email})

    if user is None:
        logging.error(f"Usuário autenticado no Firebase ({email}), mas não encontrado no Firestore local")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Usuário ({email}) não cadastrado no CRM. Fale com um admin.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_obj = User(**user)
    except Exception as e:
        logging.error(f"Erro ao instanciar modelo User para {email}: {e}")
        # Tenta fallback manual se falhar a validação estrita
        user_obj = User(
            id=user.get("id", str(uuid.uuid4())),
            username=user.get("username", email.split('@')[0]),
            email=email,
            role=user.get("role", "agent"),
            is_active=user.get("is_active", True)
        )

    # Verifica se o usuário está ativo
    if not user_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sua conta está desativada. Entre em contato com o administrador."
        )

    return user_obj


async def admin_required(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso de administrador necessário"
        )
    return current_user
