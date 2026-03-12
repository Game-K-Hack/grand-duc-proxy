from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models   import User, Role
from security import hash_password, require_permission

router = APIRouter()


class UserIn(BaseModel):
    username: str
    email:    Optional[str] = None
    password: str
    role_id:  int
    enabled:  bool = True


class UserUpdate(BaseModel):
    email:    Optional[str]  = None
    password: Optional[str]  = None
    role_id:  Optional[int]  = None
    enabled:  Optional[bool] = None


class UserOut(BaseModel):
    id:         int
    username:   str
    email:      Optional[str]
    role:       str
    role_id:    int | None
    role_name:  str
    enabled:    bool
    created_at: str
    last_login: Optional[str]


def _row_to_out(u: User, role_name: str | None) -> UserOut:
    return UserOut(
        id=u.id,
        username=u.username,
        email=u.email,
        role=u.role,
        role_id=u.role_id,
        role_name=role_name or "—",
        enabled=u.enabled,
        created_at=u.created_at.isoformat(),
        last_login=u.last_login.isoformat() if u.last_login else None,
    )


@router.get("", response_model=list[UserOut])
async def list_users(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("users.read")),
):
    # JOIN unique : 1 seule requête au lieu de N+1
    result = await db.execute(
        select(User, Role.name.label("role_name"))
        .outerjoin(Role, User.role_id == Role.id)
        .order_by(User.created_at.desc())
    )
    return [_row_to_out(row.User, row.role_name) for row in result.all()]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body:  UserIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("users.write")),
):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Ce nom d'utilisateur existe déjà")

    # Valider que le rôle existe
    role = (await db.execute(select(Role).where(Role.id == body.role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(400, "Rôle introuvable")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=role.name.lower()[:10],
        role_id=body.role_id,
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
         f"Rôle : {role.name}",
         f"Email : {user.email or '—'}"],
    ))

    return _row_to_out(user, role.name)


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body:    UserUpdate,
    db:      AsyncSession = Depends(get_db),
    _user:   User = Depends(require_permission("users.write")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")

    if body.email    is not None: user.email           = body.email
    if body.enabled  is not None: user.enabled         = body.enabled
    if body.password is not None: user.hashed_password = hash_password(body.password)
    if body.role_id  is not None:
        role = (await db.execute(select(Role).where(Role.id == body.role_id))).scalar_one_or_none()
        if not role:
            raise HTTPException(400, "Rôle introuvable")
        user.role_id = body.role_id
        user.role = role.name.lower()[:10]

    await db.commit()
    await db.refresh(user)
    # Récupérer le nom du rôle
    rn = None
    if user.role_id:
        rn = (await db.execute(select(Role.name).where(Role.id == user.role_id))).scalar_one_or_none()
    return _row_to_out(user, rn)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db:      AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("users.write")),
):
    if current.id == user_id:
        raise HTTPException(400, "Impossible de supprimer votre propre compte")
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Utilisateur introuvable")
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
