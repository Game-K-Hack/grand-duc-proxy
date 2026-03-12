"""
Paramètres globaux (SMTP) et préférences de notification par utilisateur.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

import json

from database import get_db
from models import AppSetting, FilterRule, NotificationPref, NotificationRuleWatch, User, UserTheme
from security import get_current_user, require_permission
from services.email import EVENT_LABELS, _get_smtp_config, _send_async, _html_template

router = APIRouter()


# ── Schémas ────────────────────────────────────────────────────────────────────

class SmtpConfig(BaseModel):
    host:     str
    port:     int  = 587
    user:     str  = ""
    password: str  = ""
    from_:    str  = ""       # adresse expéditeur (alias 'from' est un mot réservé)
    tls:      bool = True

class SmtpConfigOut(BaseModel):
    host:     str
    port:     int
    user:     str
    password: str           # masqué côté API
    from_:    str
    tls:      bool
    configured: bool

class TestEmailIn(BaseModel):
    to: str

class EventPref(BaseModel):
    event_type: str
    label:      str
    enabled:    bool

class RuleWatchOut(BaseModel):
    rule_id:  int
    pattern:  str
    action:   str
    description: Optional[str]
    enabled_rule: bool

class SetRuleWatchesIn(BaseModel):
    rule_ids: list[int]


# ── SMTP ───────────────────────────────────────────────────────────────────────

SMTP_KEYS = ["host", "port", "user", "password", "from", "tls"]

async def _read_smtp(db: AsyncSession) -> dict:
    rows = (await db.execute(
        select(AppSetting).where(AppSetting.key.like("smtp_%"))
    )).scalars().all()
    return {r.key.removeprefix("smtp_"): r.value for r in rows}


@router.get("/smtp", response_model=SmtpConfigOut)
async def get_smtp(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.smtp.read")),
):
    cfg = await _read_smtp(db)
    return SmtpConfigOut(
        host=cfg.get("host", ""),
        port=int(cfg.get("port", 587)),
        user=cfg.get("user", ""),
        password="••••••" if cfg.get("password") else "",
        from_=cfg.get("from", ""),
        tls=cfg.get("tls", "true").lower() == "true",
        configured=bool(cfg.get("host")),
    )


@router.put("/smtp")
async def update_smtp(
    body:  SmtpConfig,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.smtp.write")),
):
    data = {
        "smtp_host": body.host,
        "smtp_port": str(body.port),
        "smtp_user": body.user,
        "smtp_from": body.from_,
        "smtp_tls":  "true" if body.tls else "false",
    }
    # Ne pas écraser le mot de passe si masqué (non modifié)
    if body.password and not body.password.startswith("•"):
        data["smtp_password"] = body.password

    # Batch : charger tous les settings existants en 1 requête (au lieu de N)
    keys = list(data.keys())
    existing_rows = (await db.execute(
        select(AppSetting).where(AppSetting.key.in_(keys))
    )).scalars().all()
    existing_map = {s.key: s for s in existing_rows}

    for key, value in data.items():
        if key in existing_map:
            existing_map[key].value = value
        else:
            db.add(AppSetting(key=key, value=value))

    await db.commit()
    return {"ok": True}


@router.post("/smtp/test")
async def test_smtp(
    body:  TestEmailIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.smtp.write")),
):
    cfg = await _get_smtp_config()
    if not cfg:
        raise HTTPException(400, "SMTP non configuré")
    try:
        body_html = _html_template(
            "Email de test",
            ["Ce message confirme que la configuration SMTP est correcte.",
             "Grand-Duc peut envoyer des alertes."],
        )
        await _send_async(cfg, body.to, "[Grand-Duc] Email de test", body_html)
    except Exception as exc:
        raise HTTPException(502, f"Envoi échoué : {exc}")
    return {"ok": True}


# ── Préférences de notification (par utilisateur) ─────────────────────────────

@router.get("/notifications", response_model=list[EventPref])
async def get_my_prefs(
    db:   AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = {
        p.event_type: p.enabled
        for p in (await db.execute(
            select(NotificationPref).where(NotificationPref.user_id == user.id)
        )).scalars().all()
    }
    return [
        EventPref(event_type=k, label=v, enabled=rows.get(k, False))
        for k, v in EVENT_LABELS.items()
    ]


@router.put("/notifications")
async def set_my_prefs(
    body: list[EventPref],
    db:   AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    for pref in body:
        if pref.event_type not in EVENT_LABELS:
            continue
        existing = await db.get(NotificationPref, (user.id, pref.event_type))
        if existing:
            existing.enabled = pref.enabled
        else:
            db.add(NotificationPref(user_id=user.id, event_type=pref.event_type, enabled=pref.enabled))
    await db.commit()
    return {"ok": True}


# ── Règles surveillées ─────────────────────────────────────────────────────────

@router.get("/notifications/rules", response_model=list[RuleWatchOut])
async def get_my_rule_watches(
    db:   AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    watches = (await db.execute(
        select(NotificationRuleWatch).where(NotificationRuleWatch.user_id == user.id)
    )).scalars().all()
    watched_ids = {w.rule_id for w in watches}

    rules = (await db.execute(select(FilterRule).order_by(FilterRule.priority.desc()))).scalars().all()
    return [
        RuleWatchOut(
            rule_id=r.id,
            pattern=r.pattern,
            action=r.action,
            description=r.description,
            enabled_rule=r.enabled,
        )
        for r in rules if r.id in watched_ids
    ]


@router.get("/notifications/rules/available", response_model=list[RuleWatchOut])
async def get_available_rules(
    db:   AsyncSession = Depends(get_db),
    _u:   User = Depends(get_current_user),
):
    rules = (await db.execute(
        select(FilterRule).where(FilterRule.enabled == True).order_by(FilterRule.priority.desc())
    )).scalars().all()
    return [
        RuleWatchOut(rule_id=r.id, pattern=r.pattern, action=r.action,
                     description=r.description, enabled_rule=r.enabled)
        for r in rules
    ]


@router.put("/notifications/rules")
async def set_my_rule_watches(
    body: SetRuleWatchesIn,
    db:   AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current = (await db.execute(
        select(NotificationRuleWatch).where(NotificationRuleWatch.user_id == user.id)
    )).scalars().all()
    current_ids = {w.rule_id for w in current}
    new_ids = set(body.rule_ids)

    # Supprimer celles qui ne sont plus voulues
    for w in current:
        if w.rule_id not in new_ids:
            await db.delete(w)

    # Ajouter les nouvelles
    for rid in new_ids - current_ids:
        db.add(NotificationRuleWatch(user_id=user.id, rule_id=rid))

    await db.commit()
    return {"ok": True}


# ── Thème utilisateur ─────────────────────────────────────────────────────────

class ThemeIn(BaseModel):
    theme: dict | None = None


@router.get("/theme")
async def get_my_theme(
    db:   AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        row = await db.get(UserTheme, user.id)
        return {"theme": json.loads(row.theme) if row else None}
    except Exception:
        return {"theme": None}


@router.put("/theme")
async def set_my_theme(
    body: ThemeIn,
    db:   AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        row = await db.get(UserTheme, user.id)
        if body.theme:
            if row:
                row.theme = json.dumps(body.theme)
            else:
                db.add(UserTheme(user_id=user.id, theme=json.dumps(body.theme)))
        elif row:
            await db.delete(row)
        await db.commit()
    except Exception:
        pass
    return {"ok": True}
