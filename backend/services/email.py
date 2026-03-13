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

DEFAULT_EMAIL_TEMPLATE = """<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',Arial,sans-serif">
<div style="padding:32px 16px">
<div style="max-width:540px;margin:auto;background:#161b22;border-radius:12px;overflow:hidden;border:1px solid #30363d;box-shadow:0 8px 32px rgba(0,0,0,.4)">
  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1f2937 0%,#1a1f2e 100%);padding:24px 28px;border-bottom:1px solid #30363d;text-align:center">
    <img src="data:image/x-icon;base64,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" width="42" style="display:block;margin:0 auto 10px" />
    <div style="font-size:20px;font-weight:700;color:#f0883e;letter-spacing:0.5px">Grand-Duc</div>
    <div style="font-size:12px;color:#8b949e;margin-top:4px">Notification d'alerte</div>
  </div>
  <!-- Body -->
  <div style="padding:24px 28px">
    <div style="background:#1c2333;border-left:3px solid #f0883e;border-radius:0 6px 6px 0;padding:14px 18px;margin-bottom:20px">
      <p style="font-size:15px;font-weight:600;margin:0;color:#e6edf3">{{event_label}}</p>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:13px">{{details}}</table>
  </div>
  <!-- Footer -->
  <div style="padding:16px 28px;border-top:1px solid #30363d;background:#0d1117">
    <p style="margin:0;font-size:11px;color:#484f58;text-align:center">
      Envoyé le {{date}} par Grand-Duc Administration
    </p>
  </div>
</div>
</div></body></html>"""


_custom_template_cache: str | None = None
_custom_template_loaded = False


async def _get_custom_template() -> str | None:
    """Charge le template personnalisé depuis app_settings (avec cache)."""
    global _custom_template_cache, _custom_template_loaded
    if _custom_template_loaded:
        return _custom_template_cache
    try:
        async with AsyncSessionLocal() as db:
            row = await db.get(AppSetting, "email_template")
            _custom_template_cache = row.value if row else None
            _custom_template_loaded = True
    except Exception:
        pass
    return _custom_template_cache


def invalidate_template_cache():
    """Appelé après modification du template."""
    global _custom_template_cache, _custom_template_loaded
    _custom_template_cache = None
    _custom_template_loaded = False


def render_template(template: str, event_label: str, detail_lines: list[str]) -> str:
    """Remplace les placeholders {{...}} dans le template."""
    details = "".join(f"<tr><td style='padding:4px 8px;color:#8b949e'>{l}</td></tr>" for l in detail_lines)
    date_str = datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M UTC')
    html = template.replace("{{event_label}}", event_label)
    html = html.replace("{{details}}", details)
    html = html.replace("{{date}}", date_str)
    return html


async def _html_template(event_label: str, detail_lines: list[str]) -> str:
    custom = await _get_custom_template()
    template = custom if custom else DEFAULT_EMAIL_TEMPLATE
    return render_template(template, event_label, detail_lines)


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

    body = await _html_template(EVENT_LABELS.get(event_type, event_type), details)

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

            body = await _html_template("Règle de filtrage déclenchée", details)
            try:
                await _send_async(
                    cfg, user.email,
                    f"[Grand-Duc] Règle déclenchée : {rule.pattern[:40]}",
                    body,
                )
            except Exception as exc:
                logger.error("Échec alerte règle %s → %s : %s", rule.id, user.email, exc)

        await db.commit()
