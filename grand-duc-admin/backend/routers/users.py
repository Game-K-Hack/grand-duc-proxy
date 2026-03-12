from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models   import User
from security import hash_password, require_admin

router = APIRouter()


class UserIn(BaseModel):
    username: str
    email:    Optional[str] = None
    password: str
    role:     str = "viewer"
    enabled:  bool = True


class UserUpdate(BaseModel):
    email:    Optional[str] = None
    password: Optional[str] = None
    role:     Optional[str] = None
    enabled:  Optional[bool] = None


class UserOut(BaseModel):
    id:         int
    username:   str
    email:      Optional[str]
    role:       str
    enabled:    bool
    created_at: str
    last_login: Optional[str]


def user_to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        username=u.username,
        email=u.email,
        role=u.role,
        enabled=u.enabled,
        created_at=u.created_at.isoformat(),
        last_login=u.last_login.isoformat() if u.last_login else None,
    )


@router.get("", response_model=list[UserOut])
async def list_users(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [user_to_out(u) for u in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body:  UserIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Ce nom d'utilisateur existe déjà")

    if body.role not in ("admin", "viewer"):
        raise HTTPException(400, "role doit être 'admin' ou 'viewer'")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
        enabled=body.enabled,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    import asyncio
    from services.email import notify
    asyncio.create_task(notify(
        "new_account",
        f"Nouveau compte créé : {user.username}",
        [f"Nom d'utilisateur : <strong>{user.username}</strong>",
         f"Rôle : {user.role}",
         f"Email : {user.email or '—'}"],
    ))

    return user_to_out(user)


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body:    UserUpdate,
    db:      AsyncSession = Depends(get_db),
    _user:   User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")

    if body.email    is not None: user.email           = body.email
    if body.role     is not None: user.role            = body.role
    if body.enabled  is not None: user.enabled         = body.enabled
    if body.password is not None: user.hashed_password = hash_password(body.password)

    await db.commit()
    await db.refresh(user)
    return user_to_out(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db:      AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    if current.id == user_id:
        raise HTTPException(400, "Impossible de supprimer votre propre compte")
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Utilisateur introuvable")
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
