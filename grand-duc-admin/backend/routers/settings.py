"""
Paramètres globaux (SMTP) et préférences de notification par utilisateur.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

import json

logger = logging.getLogger(__name__)

from database import get_db
from models import AppSetting, FilterRule, NotificationPref, NotificationRuleWatch, User, UserTheme
from security import get_current_user, require_permission
from services.email import (
    EVENT_LABELS, _get_smtp_config, _send_async, _html_template,
    DEFAULT_EMAIL_TEMPLATE, render_template, invalidate_template_cache,
)

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
        body_html = await _html_template(
            "Email de test",
            ["Ce message confirme que la configuration SMTP est correcte.",
             "Grand-Duc peut envoyer des alertes."],
        )
        await _send_async(cfg, body.to, "[Grand-Duc] Email de test", body_html)
    except Exception as exc:
        raise HTTPException(502, f"Envoi échoué : {exc}")
    return {"ok": True}


# ── Template e-mail ───────────────────────────────────────────────────────────

class EmailTemplateIn(BaseModel):
    template: str


class EmailTemplateOut(BaseModel):
    template: str
    is_custom: bool


@router.get("/email-template", response_model=EmailTemplateOut)
async def get_email_template(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.smtp.read")),
):
    row = await db.get(AppSetting, "email_template")
    if row:
        return EmailTemplateOut(template=row.value, is_custom=True)
    return EmailTemplateOut(template=DEFAULT_EMAIL_TEMPLATE, is_custom=False)


@router.put("/email-template")
async def set_email_template(
    body:  EmailTemplateIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.smtp.write")),
):
    row = await db.get(AppSetting, "email_template")
    if row:
        row.value = body.template
    else:
        db.add(AppSetting(key="email_template", value=body.template))
    await db.commit()
    invalidate_template_cache()
    return {"ok": True}


@router.delete("/email-template")
async def reset_email_template(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.smtp.write")),
):
    row = await db.get(AppSetting, "email_template")
    if row:
        await db.delete(row)
        await db.commit()
    invalidate_template_cache()
    return {"ok": True}


class PreviewIn(BaseModel):
    template: str


@router.post("/email-template/preview")
async def preview_email_template(
    body:  PreviewIn,
    _user: User = Depends(require_permission("settings.smtp.read")),
):
    """Rendu du template avec des données fictives, pour prévisualisation."""
    sample_details = [
        "Règle : <strong>.*discord.*</strong> (action : block)",
        "3 déclenchement(s) depuis la dernière vérification",
        "&nbsp;&nbsp;• 14:32:05 — 192.168.1.42 → discord.com",
        "&nbsp;&nbsp;• 14:32:12 — 192.168.1.42 → cdn.discordapp.com",
        "&nbsp;&nbsp;• 14:33:01 — 10.0.0.15 → gateway.discord.gg",
    ]
    html = render_template(body.template, "Règle de filtrage déclenchée", sample_details)
    return {"html": html}


# ── Page de blocage ──────────────────────────────────────────────────────────

def _block_page_disk_path() -> Path | None:
    """Chemin du fichier index.html de la page de blocage sur disque."""
    from config import settings as cfg
    work_dir = getattr(cfg, "PROXY_WORK_DIR", None)
    if not work_dir:
        return None
    return Path(work_dir) / "templates" / "blocked" / "index.html"


def _read_default_block_page() -> str:
    """Lit le template par défaut depuis le disque (source du projet)."""
    # Chercher dans le répertoire du projet (2 niveaux au-dessus du backend)
    candidates = [
        Path(__file__).resolve().parents[3] / "templates" / "blocked" / "index.html",  # grand-duc/templates
        _block_page_disk_path(),
    ]
    for path in candidates:
        if path and path.is_file():
            try:
                return path.read_text(encoding="utf-8")
            except Exception:
                continue
    return "<html><body><h1>Accès bloqué</h1><p>{{blocked_url}}</p></body></html>"


def _write_block_page_to_disk(html: str):
    """Écrit le template sur disque pour que le proxy Rust le lise."""
    path = _block_page_disk_path()
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        logger.info("Page de blocage écrite sur disque : %s", path)
    except Exception as exc:
        logger.warning("Impossible d'écrire la page de blocage sur disque : %s", exc)


class BlockPageOut(BaseModel):
    template: str
    is_custom: bool


@router.get("/block-page", response_model=BlockPageOut)
async def get_block_page(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.smtp.read")),
):
    row = await db.get(AppSetting, "block_page_template")
    if row:
        return BlockPageOut(template=row.value, is_custom=True)
    return BlockPageOut(template=_read_default_block_page(), is_custom=False)


class BlockPageIn(BaseModel):
    template: str


@router.put("/block-page")
async def set_block_page(
    body:  BlockPageIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.smtp.write")),
):
    row = await db.get(AppSetting, "block_page_template")
    if row:
        row.value = body.template
    else:
        db.add(AppSetting(key="block_page_template", value=body.template))
    await db.commit()
    _write_block_page_to_disk(body.template)
    return {"ok": True}


@router.delete("/block-page")
async def reset_block_page(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.smtp.write")),
):
    row = await db.get(AppSetting, "block_page_template")
    if row:
        await db.delete(row)
        await db.commit()
    # Restaurer le fichier par défaut sur disque
    default_html = _read_default_block_page()
    _write_block_page_to_disk(default_html)
    return {"ok": True}


@router.post("/block-page/preview")
async def preview_block_page(
    body:  BlockPageIn,
    _user: User = Depends(require_permission("settings.smtp.read")),
):
    """Retourne le HTML avec une URL bloquée fictive injectée (comme le proxy)."""
    sample_url = "https://discord.com/channels/example"
    injection = (
        '<base href="https://grand-duc.proxy/blocked/">'
        f'<script>window.__BLOCKED_URL__ = "{sample_url}";</script>'
    )
    html = body.template
    if "<head>" in html:
        pos = html.index("<head>") + len("<head>")
        html = html[:pos] + injection + html[pos:]
    elif "<head " in html:
        pos = html.index("<head ")
        end = html.index(">", pos) + 1
        html = html[:end] + injection + html[end:]
    else:
        html = injection + html
    return {"html": html}


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
