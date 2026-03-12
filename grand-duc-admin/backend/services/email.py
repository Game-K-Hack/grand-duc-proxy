"""
Service d'envoi d'emails d'alerte.
La configuration SMTP est lue depuis app_settings (clés : smtp_*).
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy import func as sa_func, select, update

from database import AsyncSessionLocal
from models import AppSetting, AccessLog, FilterRule, NotificationPref, NotificationRuleWatch, User

logger = logging.getLogger(__name__)

# ── Types d'événements ─────────────────────────────────────────────────────────

EVENT_LABELS = {
    "certificate":    "Changement de certificat CA",
    "proxy_restart":  "Redémarrage du proxy",
    "killswitch":     "Activation / désactivation du Killswitch",
    "new_account":    "Nouveau compte administrateur",
    "rule_triggered": "Règle de filtrage déclenchée",
    "rmm_sync_error": "Erreur de synchronisation RMM",
}


# ── Lecture config SMTP ────────────────────────────────────────────────────────

async def _get_smtp_config() -> dict | None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(AppSetting).where(AppSetting.key.like("smtp_%"))
        )).scalars().all()
    cfg = {r.key.removeprefix("smtp_"): r.value for r in rows}
    if not cfg.get("host"):
        return None
    return cfg


# ── Envoi bas niveau ───────────────────────────────────────────────────────────

def _send_sync(cfg: dict, to: str, subject: str, body_html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg.get("from") or cfg.get("user", "grand-duc@localhost")
    msg["To"]      = to
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    host = cfg["host"]
    port = int(cfg.get("port", 587))
    use_tls = cfg.get("tls", "true").lower() == "true"

    if use_tls and port == 465:
        # Port 465 = SSL implicite (SMTP_SSL)
        server = smtplib.SMTP_SSL(host, port, timeout=10)
    elif use_tls:
        # Port 587 = STARTTLS
        server = smtplib.SMTP(host, port, timeout=10)
        server.ehlo()
        server.starttls()
    else:
        server = smtplib.SMTP(host, port, timeout=10)
        server.ehlo()

    if cfg.get("user") and cfg.get("password"):
        server.login(cfg["user"], cfg["password"])

    server.sendmail(msg["From"], [to], msg.as_string())
    server.quit()


async def _send_async(cfg: dict, to: str, subject: str, body_html: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_sync, cfg, to, subject, body_html)


# ── Template HTML ─────────────────────────────────────────────────────────────

def _html_template(event_label: str, detail_lines: list[str]) -> str:
    details = "".join(f"<tr><td style='padding:4px 8px;color:#8b949e'>{l}</td></tr>" for l in detail_lines)
    return f"""<!DOCTYPE html><html><body style="background:#0d1117;color:#c9d1d9;font-family:Arial,sans-serif;padding:24px">
<div style="max-width:520px;margin:auto;background:#161b22;border-radius:10px;overflow:hidden;border:1px solid #30363d">
  <div style="background:#1f2937;padding:18px 24px;border-bottom:1px solid #30363d">
    <span style="font-size:18px;font-weight:700;color:#58a6ff">&#x1F989; Grand-Duc</span>
    <span style="margin-left:12px;color:#8b949e;font-size:13px">Alerte</span>
  </div>
  <div style="padding:20px 24px">
    <p style="font-size:15px;font-weight:600;margin-bottom:12px;color:#e6edf3">{event_label}</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">{details}</table>
    <p style="margin-top:18px;font-size:11px;color:#484f58">
      Envoyé le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M UTC')} par Grand-Duc Admin.
    </p>
  </div>
</div></body></html>"""


# ── Envoi aux abonnés ──────────────────────────────────────────────────────────

async def notify(event_type: str, subject: str, details: list[str]):
    """Envoie l'alerte à tous les utilisateurs abonnés à cet événement."""
    cfg = await _get_smtp_config()
    if not cfg:
        return  # SMTP non configuré

    async with AsyncSessionLocal() as db:
        # Utilisateurs abonnés à cet événement
        rows = (await db.execute(
            select(User).join(
                NotificationPref,
                (NotificationPref.user_id == User.id) &
                (NotificationPref.event_type == event_type) &
                (NotificationPref.enabled == True)
            ).where(User.enabled == True, User.email.isnot(None))
        )).scalars().all()

    body = _html_template(EVENT_LABELS.get(event_type, event_type), details)

    for user in rows:
        try:
            await _send_async(cfg, user.email, f"[Grand-Duc] {subject}", body)
            logger.info("Notification '%s' envoyée à %s", event_type, user.email)
        except Exception as exc:
            logger.error("Échec notification '%s' → %s : %s", event_type, user.email, exc)


# ── Surveillance des règles déclenchées ───────────────────────────────────────

async def check_rule_triggers():
    """
    Tâche de fond : vérifie les nouveaux logs d'accès contre les règles surveillées
    et envoie des alertes si une règle configurée a été déclenchée.
    """
    cfg = await _get_smtp_config()
    if not cfg:
        return

    async with AsyncSessionLocal() as db:
        watches = (await db.execute(select(NotificationRuleWatch))).scalars().all()
        if not watches:
            return

        # Regrouper les watches par rule_id pour éviter les doublons de requêtes
        rule_ids = list({w.rule_id for w in watches})
        rules = {
            r.id: r for r in (await db.execute(
                select(FilterRule).where(FilterRule.id.in_(rule_ids))
            )).scalars().all()
        }

        # ID max actuel des logs — le curseur avancera toujours jusqu'ici
        current_max_id = (await db.execute(
            select(sa_func.coalesce(sa_func.max(AccessLog.id), 0))
        )).scalar()

        for watch in watches:
            rule = rules.get(watch.rule_id)
            if not rule:
                continue

            if watch.last_notified_log_id >= current_max_id:
                continue

            # Filtrer directement en SQL avec le regex PostgreSQL (~*)
            try:
                matched = (await db.execute(
                    select(AccessLog)
                    .where(
                        AccessLog.id > watch.last_notified_log_id,
                        AccessLog.id <= current_max_id,
                        AccessLog.url.op("~*")(rule.pattern),
                    )
                    .order_by(AccessLog.id)
                    .limit(50)
                )).scalars().all()
            except Exception:
                # Regex invalide en SQL — fallback silencieux
                matched = []

            # Toujours avancer le curseur au max actuel, même sans match
            await db.execute(
                update(NotificationRuleWatch)
                .where(
                    NotificationRuleWatch.user_id == watch.user_id,
                    NotificationRuleWatch.rule_id == watch.rule_id,
                )
                .values(last_notified_log_id=current_max_id)
            )

            if not matched:
                continue

            # Récupérer l'utilisateur pour l'email
            user = await db.get(User, watch.user_id)
            if not user or not user.email or not user.enabled:
                continue

            # Vérifier que l'abonnement rule_triggered est actif
            pref = await db.get(NotificationPref, (watch.user_id, "rule_triggered"))
            if not pref or not pref.enabled:
                continue

            details = [
                f"Règle : <strong>{rule.pattern}</strong> (action : {rule.action})",
                f"{len(matched)} déclenchement(s) depuis la dernière vérification",
            ]
            for log in matched[:5]:
                details.append(
                    f"&nbsp;&nbsp;• {log.accessed_at.strftime('%H:%M:%S')} — "
                    f"{log.client_ip or '?'} → {log.host}"
                )
            if len(matched) > 5:
                details.append(f"&nbsp;&nbsp;… et {len(matched) - 5} de plus")

            body = _html_template("Règle de filtrage déclenchée", details)
            try:
                await _send_async(
                    cfg, user.email,
                    f"[Grand-Duc] Règle déclenchée : {rule.pattern[:40]}",
                    body,
                )
            except Exception as exc:
                logger.error("Échec alerte règle %s → %s : %s", rule.id, user.email, exc)

        await db.commit()
