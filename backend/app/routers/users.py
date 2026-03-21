import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from firebase_admin import auth

from app.auth.dependencies import get_current_user, admin_required, get_password_hash, verify_password
from app.db.firestore_wrapper import get_db
from app.models.user import User, UserCreate, UserUpdate, PasswordChange, AgentStatus

router = APIRouter(tags=["users"])
db = get_db()


# ---------------------------------------------------------
# AUTH endpoints (formerly auth.py)
# ---------------------------------------------------------

@router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate, admin_user: User = Depends(admin_required)):
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    try:
        fb_user = await asyncio.to_thread(
            auth.create_user,
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.full_name
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro no Firebase: {str(e)}")

    new_user = User(
        id=user_data.username,
        uid=fb_user.uid,
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        role=user_data.role or "agent",
        is_active=True
    )
    user_dict = new_user.dict()
    await db.users.insert_one(user_dict)
    return new_user


@router.post("/auth/login", deprecated=True)
async def login_user():
    raise HTTPException(status_code=410, detail="Use o fluxo de autenticação Firebase no frontend.")


@router.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------
# PROFILE endpoints (formerly agent.py)
# ---------------------------------------------------------

@router.put("/profile/update", response_model=User)
async def update_profile(profile_data: UserUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in profile_data.dict().items() if v is not None}

    if "username" in update_data:
        existing = await db.users.find_one({"username": update_data["username"]})
        if existing and existing.get("id") != current_user.id:
            raise HTTPException(status_code=400, detail="Nome de usuário já cadastrado")

    if "email" in update_data:
        existing = await db.users.find_one({"email": update_data["email"]})
        if existing and existing.get("id") != current_user.id:
            raise HTTPException(status_code=400, detail="Email já cadastrado")

    if update_data:
        if "username" in update_data and update_data["username"] != current_user.id:
            new_id = update_data["username"]
            old_id = current_user.id

            full_data = await db.users.find_one({"id": old_id})
            full_data.update(update_data)
            full_data["id"] = new_id

            await db.users.insert_one(full_data)
            await db.users.delete_one({"id": old_id})

            updated_user = await db.users.find_one({"id": new_id})
            return User(**updated_user)
        else:
            await db.users.update_one({"id": current_user.id}, {"$set": update_data})

    updated_user = await db.users.find_one({"id": current_user.id})
    return User(**updated_user)


@router.put("/profile/change-password")
async def change_password(password_data: PasswordChange, current_user: User = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user.id})
    if not verify_password(password_data.current_password, user["password"]):
        raise HTTPException(status_code=400, detail="A senha atual está incorreta")

    new_hashed_password = get_password_hash(password_data.new_password)
    await db.users.update_one({"id": current_user.id}, {"$set": {"password": new_hashed_password}})
    return {"success": True, "message": "Password changed successfully"}


# ---------------------------------------------------------
# AGENT endpoints (formerly agent.py)
# ---------------------------------------------------------

@router.put("/agent/status")
async def update_agent_status(status_data: AgentStatus, current_user: User = Depends(get_current_user)):
    if current_user.id != status_data.agent_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Só é possível atualizar seu próprio status")
    
    update_data = {"status": status_data.status, "last_activity": datetime.now(timezone.utc)}
    await db.users.update_one({"id": status_data.agent_id}, {"$set": update_data})
    return {"success": True, "status": status_data.status}


@router.get("/agent/my-status")
async def get_my_status(current_user: User = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user.id})
    return {"status": user.get("status", "offline")}


# ---------------------------------------------------------
# ADMIN USERS endpoints (formerly admin.py)
# ---------------------------------------------------------

@router.get("/admin/users", response_model=List[User])
async def get_all_users(admin_user: User = Depends(admin_required)):
    users_data = await db.users.find().to_list(1000)
    valid_users = []
    for u_dict in users_data:
        try:
            if not u_dict.get("username") or not u_dict.get("email"):
                continue
            valid_users.append(User(**u_dict))
        except Exception:
            continue
    return valid_users


@router.post("/admin/users", response_model=User)
async def create_user_admin(user_data: UserCreate, admin_user: User = Depends(admin_required)):
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    try:
        fb_user = await asyncio.to_thread(
            auth.create_user,
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.full_name
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro no Firebase: {str(e)}")

    new_user = User(
        id=user_data.username,
        uid=fb_user.uid,
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        role=user_data.role or "agent",
        is_active=True
    )
    user_dict = new_user.dict()
    await db.users.insert_one(user_dict)
    return new_user


@router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, admin_user: User = Depends(admin_required)):
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Não é possível excluir sua própria conta")

    try:
        await asyncio.to_thread(auth.delete_user, user_id)
    except Exception:
        pass

    result = await db.users.delete_one({"id": user_id})
    if result.get('deleted_count') == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado localmente")
    return {"success": True, "message": "Usuário excluído com sucesso"}


@router.post("/admin/users/{user_id}/reset-password")
async def reset_password(user_id: str, password_data: dict, admin_user: User = Depends(admin_required)):
    new_password = password_data.get("password")
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="A nova senha deve ter pelo menos 6 caracteres")

    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    try:
        await asyncio.to_thread(auth.update_user, user_id, password=new_password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro no Firebase: {str(e)}")

    hashed_password = get_password_hash(new_password)
    await db.users.update_one({"id": user_id}, {"$set": {"password": hashed_password}})
    return {"success": True, "message": "Senha resetada com sucesso"}


@router.put("/admin/users/{user_id}", response_model=User)
async def update_user(user_id: str, user_data: UserUpdate, admin_user: User = Depends(admin_required)):
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Use profile update endpoint for your own data")

    update_data = {k: v for k, v in user_data.dict().items() if v is not None}

    if "username" in update_data:
        existing = await db.users.find_one({"username": update_data["username"]})
        if existing and existing.get("id") != user_id:
            raise HTTPException(status_code=400, detail="Nome de usuário já cadastrado")

    if "email" in update_data:
        existing = await db.users.find_one({"email": update_data["email"]})
        if existing and existing.get("id") != user_id:
            raise HTTPException(status_code=400, detail="Email já cadastrado")

    if update_data:
        result = await db.users.update_one({"id": user_id}, {"$set": update_data})
        if result.get('matched_count') == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if "username" in update_data and update_data["username"] != user_id:
        new_id = update_data["username"]
        full_data = await db.users.find_one({"id": user_id})
        full_data["id"] = new_id
        await db.users.insert_one(full_data)
        await db.users.delete_one({"id": user_id})
        updated_user = await db.users.find_one({"id": new_id})
        return User(**updated_user)

    updated_user = await db.users.find_one({"id": user_id})
    return User(**updated_user)
