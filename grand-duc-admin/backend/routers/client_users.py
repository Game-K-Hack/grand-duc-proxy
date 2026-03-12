from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models   import ClientUser, ClientGroup, ClientUserGroups, GroupRule, FilterRule
from security import require_permission
from models   import User

router = APIRouter()


# ── Schémas ───────────────────────────────────────────────────────────────────

class ClientUserIn(BaseModel):
    ip_address: str
    label:      Optional[str] = None
    hostname:   Optional[str] = None
    os:         Optional[str] = None


class ClientUserUpdate(BaseModel):
    label:    Optional[str] = None
    hostname: Optional[str] = None
    os:       Optional[str] = None


class GroupBrief(BaseModel):
    id:   int
    name: str


class ClientUserOut(BaseModel):
    id:                 int
    ip_address:         str
    label:              Optional[str]
    hostname:           Optional[str]
    os:                 Optional[str]
    source:             str
    last_seen_rmm:      Optional[str]
    rmm_integration_id: Optional[int]
    groups:             list[GroupBrief]
    created_at:         str


class SetGroupsIn(BaseModel):
    group_ids: list[int]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_user_or_404(db, user_id: int) -> ClientUser:
    u = (await db.execute(select(ClientUser).where(ClientUser.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(404, "Utilisateur introuvable")
    return u


async def fetch_user_groups(db, user_id: int) -> list[GroupBrief]:
    rows = (await db.execute(
        select(ClientGroup)
        .join(ClientUserGroups, ClientGroup.id == ClientUserGroups.group_id)
        .where(ClientUserGroups.user_id == user_id)
        .order_by(ClientGroup.name)
    )).scalars().all()
    return [GroupBrief(id=g.id, name=g.name) for g in rows]


async def build_user_out(db, u: ClientUser) -> ClientUserOut:
    return ClientUserOut(
        id=u.id, ip_address=u.ip_address, label=u.label,
        hostname=u.hostname, os=u.os, source=u.source,
        last_seen_rmm=u.last_seen_rmm.isoformat() if u.last_seen_rmm else None,
        rmm_integration_id=u.rmm_integration_id,
        groups=await fetch_user_groups(db, u.id),
        created_at=u.created_at.isoformat(),
    )


# ── CRUD utilisateurs ─────────────────────────────────────────────────────────

@router.get("", response_model=list[ClientUserOut])
async def list_client_users(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_users.read")),
):
    users = (await db.execute(
        select(ClientUser).order_by(ClientUser.label.nullslast(), ClientUser.ip_address)
    )).scalars().all()
    return [await build_user_out(db, u) for u in users]


@router.post("", response_model=ClientUserOut, status_code=201)
async def create_client_user(
    body:  ClientUserIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_users.write")),
):
    if (await db.execute(select(ClientUser).where(ClientUser.ip_address == body.ip_address))).scalar_one_or_none():
        raise HTTPException(409, "Cette adresse IP est déjà enregistrée")
    u = ClientUser(ip_address=body.ip_address, label=body.label, hostname=body.hostname, os=body.os)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return await build_user_out(db, u)


@router.put("/{user_id}", response_model=ClientUserOut)
async def update_client_user(
    user_id: int, body: ClientUserUpdate,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_users.write")),
):
    u = await get_user_or_404(db, user_id)
    if body.label    is not None: u.label    = body.label
    if body.hostname is not None: u.hostname = body.hostname
    if body.os       is not None: u.os       = body.os
    await db.commit()
    await db.refresh(u)
    return await build_user_out(db, u)


@router.delete("/{user_id}", status_code=204)
async def delete_client_user(
    user_id: int,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_users.write")),
):
    await get_user_or_404(db, user_id)
    await db.execute(delete(ClientUser).where(ClientUser.id == user_id))
    await db.commit()


# ── Gestion des groupes d'un utilisateur ─────────────────────────────────────

@router.get("/{user_id}/groups", response_model=list[GroupBrief])
async def get_user_groups(
    user_id: int,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_users.read")),
):
    await get_user_or_404(db, user_id)
    return await fetch_user_groups(db, user_id)


@router.put("/{user_id}/groups", response_model=list[GroupBrief])
async def set_user_groups(
    user_id: int, body: SetGroupsIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_users.write")),
):
    """Remplace entièrement la liste des groupes de l'utilisateur."""
    await get_user_or_404(db, user_id)
    # Supprime toutes les associations existantes
    await db.execute(delete(ClientUserGroups).where(ClientUserGroups.user_id == user_id))
    # Recrée avec les nouveaux group_ids
    for gid in set(body.group_ids):
        db.add(ClientUserGroups(user_id=user_id, group_id=gid))
    await db.commit()
    return await fetch_user_groups(db, user_id)


# ── Endpoint de test d'accès ──────────────────────────────────────────────────

class TestAccessIn(BaseModel):
    user_id: int
    url:     str


class RuleMatch(BaseModel):
    rule_id:       int
    pattern:       str
    action:        str
    group_id:      Optional[int]
    group_name:    Optional[str]
    source:        str   # "group" | "global"


class TestAccessOut(BaseModel):
    url:     str
    blocked: bool
    reason:  Optional[RuleMatch]   # None = aucune règle ne correspond (autorisé)
    user_ip: str
    user_label: Optional[str]
    groups:  list[str]


@router.post("/test-access", response_model=TestAccessOut)
async def test_access(
    body: TestAccessIn,
    db:   AsyncSession = Depends(get_db),
    _u:   User = Depends(require_permission("test_access.use")),
):
    import re

    # Récupère l'utilisateur
    u = await get_user_or_404(db, body.user_id)
    user_groups = await fetch_user_groups(db, body.user_id)
    group_ids = [g.id for g in user_groups]

    # Toutes les règles globales actives, triées par priorité
    all_rules = (await db.execute(
        select(FilterRule)
        .where(FilterRule.enabled == True)
        .order_by(FilterRule.priority.desc())
    )).scalars().all()

    # Index des group_rules : rule_id → (group_id, group_name) du premier groupe l'ayant activée
    # L'action vient de la règle globale (FilterRule.action), pas du groupe.
    group_rule_first: dict[int, tuple[int, str]] = {}
    activated_rule_ids: set[int] = set()
    if group_ids:
        rows = (await db.execute(
            select(GroupRule, ClientGroup.name.label("gname"))
            .join(ClientGroup, GroupRule.group_id == ClientGroup.id)
            .where(GroupRule.group_id.in_(group_ids))
        )).all()
        for r in rows:
            rid = r.GroupRule.rule_id
            activated_rule_ids.add(rid)
            if rid not in group_rule_first:
                group_rule_first[rid] = (r.GroupRule.group_id, r.gname)

    url = body.url

    # ── Groupes explicites ────────────────────────────────────────────────────
    # Logique identique au proxy Rust : les règles sont parcourues par priorité
    # croissante. La première règle qui matche ET active dans au moins un groupe
    # gagne — qu'elle soit block ou allow.
    if group_ids:
        for rule in all_rules:
            try:
                matches = bool(re.search(rule.pattern, url, re.IGNORECASE))
            except re.error:
                continue
            if not matches or rule.id not in activated_rule_ids:
                continue

            gid, gname = group_rule_first[rule.id]
            return TestAccessOut(
                url=url, blocked=(rule.action == "block"),
                reason=RuleMatch(
                    rule_id=rule.id, pattern=rule.pattern, action=rule.action,
                    group_id=gid, group_name=gname, source="group",
                ),
                user_ip=u.ip_address, user_label=u.label,
                groups=[g.name for g in user_groups],
            )

        # Aucune règle de groupe ne correspond → autorisé
        return TestAccessOut(
            url=url, blocked=False, reason=None,
            user_ip=u.ip_address, user_label=u.label,
            groups=[g.name for g in user_groups],
        )

    # ── Groupe par défaut / règle globale (utilisateur sans groupe explicite) ──
    for rule in all_rules:
        try:
            matches = bool(re.search(rule.pattern, url, re.IGNORECASE))
        except re.error:
            continue
        if not matches:
            continue

        return TestAccessOut(
            url=url, blocked=(rule.action == "block"),
            reason=RuleMatch(
                rule_id=rule.id, pattern=rule.pattern, action=rule.action,
                group_id=None, group_name=None, source="global",
            ),
            user_ip=u.ip_address, user_label=u.label,
            groups=[g.name for g in user_groups],
        )

    # Aucune règle ne correspond → autorisé
    return TestAccessOut(
        url=url, blocked=False, reason=None,
        user_ip=u.ip_address, user_label=u.label,
        groups=[g.name for g in user_groups],
    )