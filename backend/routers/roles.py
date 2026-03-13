"""CRUD des rôles et liste des permissions disponibles."""

import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from database    import get_db
from models      import Role, User
from security    import require_permission, get_current_user
from permissions import ALL_PERMISSIONS, PERMISSION_LABELS

router = APIRouter()


# ── Schémas ──────────────────────────────────────────────────────────────────

class RoleOut(BaseModel):
    id:          int
    name:        str
    description: str | None
    permissions: dict
    is_builtin:  bool
    user_count:  int = 0

class RoleIn(BaseModel):
    name:        str
    description: str | None = None
    permissions: dict[str, bool]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/permissions")
async def list_permissions(_: User = Depends(get_current_user)):
    """Renvoie les permissions groupées par section → fonctionnalité → actions."""
    result: dict[str, dict[str, list]] = {}
    for key in ALL_PERMISSIONS:
        info = PERMISSION_LABELS.get(key, {"section": key, "feature": key, "action": key})
        sec = info["section"]
        feat = info["feature"]
        result.setdefault(sec, {}).setdefault(feat, []).append({
            "key": key,
            "action": info["action"],
        })
    return result


@router.get("", response_model=list[RoleOut])
async def list_roles(
    _: User = Depends(require_permission("roles.read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role).order_by(Role.id))
    roles = result.scalars().all()

    # Compter les utilisateurs par rôle
    count_result = await db.execute(
        select(User.role_id, sa_func.count()).group_by(User.role_id)
    )
    counts = dict(count_result.all())

    out = []
    for r in roles:
        out.append(RoleOut(
            id=r.id,
            name=r.name,
            description=r.description,
            permissions=json.loads(r.permissions),
            is_builtin=r.is_builtin,
            user_count=counts.get(r.id, 0),
        ))
    return out


@router.post("", response_model=RoleOut, status_code=201)
async def create_role(
    body: RoleIn,
    _: User = Depends(require_permission("roles.write")),
    db: AsyncSession = Depends(get_db),
):
    # Valider que les clés sont connues
    invalid = [k for k in body.permissions if k not in ALL_PERMISSIONS]
    if invalid:
        raise HTTPException(400, f"Permissions inconnues : {invalid}")

    role = Role(
        name=body.name,
        description=body.description,
        permissions=json.dumps({k: v for k, v in body.permissions.items() if v}),
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return RoleOut(
        id=role.id, name=role.name, description=role.description,
        permissions=json.loads(role.permissions), is_builtin=False, user_count=0,
    )


@router.put("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    body: RoleIn,
    _: User = Depends(require_permission("roles.write")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(404, "Rôle introuvable")

    # Protéger le nom des rôles built-in
    if role.is_builtin and body.name != role.name:
        raise HTTPException(400, "Impossible de renommer un rôle système")

    # Protéger les permissions du rôle Administrateur built-in
    if role.is_builtin and role.name == "Administrateur":
        raise HTTPException(400, "Impossible de modifier les permissions du rôle Administrateur")

    invalid = [k for k in body.permissions if k not in ALL_PERMISSIONS]
    if invalid:
        raise HTTPException(400, f"Permissions inconnues : {invalid}")

    role.name = body.name
    role.description = body.description
    role.permissions = json.dumps({k: v for k, v in body.permissions.items() if v})
    await db.commit()
    await db.refresh(role)

    count_result = await db.execute(
        select(sa_func.count()).where(User.role_id == role.id)
    )
    user_count = count_result.scalar() or 0

    return RoleOut(
        id=role.id, name=role.name, description=role.description,
        permissions=json.loads(role.permissions), is_builtin=role.is_builtin,
        user_count=user_count,
    )


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    _: User = Depends(require_permission("roles.write")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(404, "Rôle introuvable")
    if role.is_builtin:
        raise HTTPException(400, "Impossible de supprimer un rôle système")

    # Vérifier qu'aucun utilisateur n'a ce rôle
    count_result = await db.execute(
        select(sa_func.count()).where(User.role_id == role.id)
    )
    if count_result.scalar():
        raise HTTPException(400, "Ce rôle est encore assigné à des utilisateurs")

    await db.delete(role)
    await db.commit()
    return {"ok": True}
