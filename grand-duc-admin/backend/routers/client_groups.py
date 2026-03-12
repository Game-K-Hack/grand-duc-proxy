from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models   import ClientGroup, ClientUserGroups, GroupRule, FilterRule
from security import require_permission
from models   import User

router = APIRouter()


# ── Schémas ───────────────────────────────────────────────────────────────────

class GroupIn(BaseModel):
    name:        str
    description: Optional[str] = None


class GroupOut(BaseModel):
    id:           int
    name:         str
    description:  Optional[str]
    is_default:   bool = False
    created_at:   str
    member_count: int = 0
    rule_count:   int = 0


class GroupRuleIn(BaseModel):
    rule_id: int
    action:  str   # 'block' | 'allow'


class GroupRuleOut(BaseModel):
    id:           int
    rule_id:      int
    rule_pattern: str
    rule_description: Optional[str]
    rule_priority: int
    global_action: str   # action de la règle globale
    action:        str   # action dans ce groupe


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_group_or_404(db, group_id: int) -> ClientGroup:
    g = (await db.execute(select(ClientGroup).where(ClientGroup.id == group_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Groupe introuvable")
    return g


# ── CRUD groupes ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[GroupOut])
async def list_groups(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_groups.read")),
):
    groups = (await db.execute(
        select(ClientGroup).order_by(ClientGroup.is_default.desc(), ClientGroup.name)
    )).scalars().all()

    # Compte membres par groupe
    mc = dict((await db.execute(
        select(ClientUserGroups.group_id, func.count().label("n"))
        .group_by(ClientUserGroups.group_id)
    )).all())

    # Compte règles par groupe
    rc = dict((await db.execute(
        select(GroupRule.group_id, func.count().label("n"))
        .group_by(GroupRule.group_id)
    )).all())

    return [
        GroupOut(
            id=g.id, name=g.name, description=g.description,
            is_default=g.is_default,
            created_at=g.created_at.isoformat(),
            member_count=mc.get(g.id, 0),
            rule_count=rc.get(g.id, 0),
        )
        for g in groups
    ]


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(
    body:  GroupIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_groups.write")),
):
    if (await db.execute(select(ClientGroup).where(ClientGroup.name == body.name))).scalar_one_or_none():
        raise HTTPException(409, "Un groupe avec ce nom existe déjà")
    g = ClientGroup(name=body.name, description=body.description)
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return GroupOut(id=g.id, name=g.name, description=g.description,
                    created_at=g.created_at.isoformat())


@router.put("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: int, body: GroupIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_groups.write")),
):
    g = await get_group_or_404(db, group_id)
    g.name = body.name
    g.description = body.description
    await db.commit()
    await db.refresh(g)
    return GroupOut(id=g.id, name=g.name, description=g.description,
                    created_at=g.created_at.isoformat())


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: int,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_groups.write")),
):
    g = await get_group_or_404(db, group_id)
    if g.is_default:
        raise HTTPException(400, "Le groupe par défaut ne peut pas être supprimé")
    await db.execute(delete(ClientGroup).where(ClientGroup.id == group_id))
    await db.commit()


# ── Règles d'un groupe ────────────────────────────────────────────────────────

@router.get("/{group_id}/rules", response_model=list[GroupRuleOut])
async def list_group_rules(
    group_id: int,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_groups.read")),
):
    await get_group_or_404(db, group_id)
    rows = (await db.execute(
        select(GroupRule, FilterRule)
        .join(FilterRule, GroupRule.rule_id == FilterRule.id)
        .where(GroupRule.group_id == group_id)
        .order_by(FilterRule.priority)
    )).all()
    return [
        GroupRuleOut(
            id=r.GroupRule.id,
            rule_id=r.GroupRule.rule_id,
            rule_pattern=r.FilterRule.pattern,
            rule_description=r.FilterRule.description,
            rule_priority=r.FilterRule.priority,
            global_action=r.FilterRule.action,
            action=r.GroupRule.action,
        )
        for r in rows
    ]


@router.post("/{group_id}/rules", response_model=GroupRuleOut, status_code=201)
async def add_group_rule(
    group_id: int, body: GroupRuleIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_groups.write")),
):
    await get_group_or_404(db, group_id)
    if body.action not in ("block", "allow"):
        raise HTTPException(400, "action doit être 'block' ou 'allow'")

    rule = (await db.execute(select(FilterRule).where(FilterRule.id == body.rule_id))).scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Règle introuvable")

    # Upsert
    existing = (await db.execute(
        select(GroupRule).where(GroupRule.group_id == group_id, GroupRule.rule_id == body.rule_id)
    )).scalar_one_or_none()

    if existing:
        existing.action = body.action
        await db.commit()
        gr = existing
    else:
        gr = GroupRule(group_id=group_id, rule_id=body.rule_id, action=body.action)
        db.add(gr)
        await db.commit()
        await db.refresh(gr)

    return GroupRuleOut(
        id=gr.id, rule_id=gr.rule_id,
        rule_pattern=rule.pattern, rule_description=rule.description,
        rule_priority=rule.priority, global_action=rule.action, action=gr.action,
    )


@router.delete("/{group_id}/rules/{gr_id}", status_code=204)
async def delete_group_rule(
    group_id: int, gr_id: int,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("client_groups.write")),
):
    await db.execute(
        delete(GroupRule).where(GroupRule.id == gr_id, GroupRule.group_id == group_id)
    )
    await db.commit()