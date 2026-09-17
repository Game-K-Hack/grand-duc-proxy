"""
Gestion des adresses IP des postes clients.

Les postes ont des IP attribuées par DHCP qui tournent. L'identité d'un poste
est son `client_users.id`, jamais son IP : celle-ci n'est qu'un attribut daté,
dont l'historique complet vit dans `client_user_ips`.

Ce module est le SEUL endroit autorisé à écrire `client_users.ip_address`, afin
que la colonne (« IP courante », lue par le proxy Rust) et la période ouverte de
l'historique ne puissent jamais diverger. Appelé par le routeur client_users et
par la synchro RMM.

Aucune fonction ne commit : l'appelant maîtrise la transaction.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models import AccessLog, ClientUser, ClientUserIp

logger = logging.getLogger(__name__)


class IpConflict(Exception):
    """L'IP visée est déjà détenue par un autre poste (et force=False)."""

    def __init__(self, ip: str, holder: ClientUser):
        self.ip = ip
        self.holder = holder
        super().__init__(f"L'adresse {ip} est déjà attribuée au poste #{holder.id}")


class IpTaken(Exception):
    """L'IP a été prise par une requête concurrente entre-temps."""

    def __init__(self, ip: str):
        self.ip = ip
        super().__init__(f"L'adresse {ip} vient d'être attribuée à un autre poste")


@dataclass
class IpChangeResult:
    changed:      bool
    previous_ip:  str | None
    new_ip:       str | None
    released_from: ClientUser | None = None   # poste dépossédé lors d'un transfert
    logs_linked:  int = 0


def normalize_ip(raw: str) -> str:
    """Forme canonique d'une IP.

    Le proxy Rust écrit `ctx.client_addr.ip().to_string()`, donc la forme
    canonique. Sans normalisation ici, « 192.168.001.010 » ou « FE80::1 » saisis
    à la main ne matcheraient jamais ce que le proxy enregistre.
    """
    v = (raw or "").strip()
    if "%" in v:
        raise ValueError(f"Adresse IP à zone non supportée : {v}")
    return str(ipaddress.ip_address(v))


async def _close_current_period(db: AsyncSession, user_id: int, note: str | None = None) -> None:
    values: dict = {"released_at": datetime.now(timezone.utc)}
    if note:
        values["note"] = note
    await db.execute(
        update(ClientUserIp)
        .where(ClientUserIp.user_id == user_id, ClientUserIp.released_at.is_(None))
        .values(**values)
    )


async def change_client_user_ip(
    db:     AsyncSession,
    user:   ClientUser,
    new_ip: str | None,
    source: str = "manual",
    force:  bool = False,
    note:   str | None = None,
) -> IpChangeResult:
    """Attribue `new_ip` au poste (ou le prive d'IP si `new_ip` est None).

    Ne touche JAMAIS à `client_user_groups` : les droits du poste sont portés
    par son id, ils survivent donc au changement d'IP sans rien faire.

    Lève `IpConflict` si l'IP est détenue par un autre poste et `force=False`,
    `IpTaken` en cas de course avec une requête concurrente.
    """
    normalized = normalize_ip(new_ip) if new_ip is not None else None

    # Verrou sur le poste : sérialise les appels concurrents le visant.
    locked = (await db.execute(
        select(ClientUser).where(ClientUser.id == user.id).with_for_update()
    )).scalar_one()
    previous_ip = locked.ip_address

    # No-op. Indispensable : sans lui, une synchro RMM périodique créerait une
    # période d'historique à chaque exécution.
    if normalized == previous_ip:
        return IpChangeResult(changed=False, previous_ip=previous_ip, new_ip=normalized)

    released_from: ClientUser | None = None

    if normalized is not None:
        holder = (await db.execute(
            select(ClientUser)
            .where(ClientUser.ip_address == normalized, ClientUser.id != locked.id)
            .with_for_update()
        )).scalar_one_or_none()

        if holder is not None:
            if not force:
                raise IpConflict(normalized, holder)
            # Transfert : on dépossède l'ancien détenteur sans jamais le
            # supprimer — il conserve groupes, historique et logs.
            await _close_current_period(db, holder.id, note=f"transférée vers #{locked.id}")
            holder.ip_address = None
            await db.flush()
            released_from = holder
            logger.info(
                "IP %s transférée du poste #%s vers le poste #%s", normalized, holder.id, locked.id
            )

    await _close_current_period(db, locked.id)

    if normalized is not None:
        db.add(ClientUserIp(user_id=locked.id, ip_address=normalized, source=source, note=note))

    locked.ip_address = normalized

    try:
        await db.flush()
    except IntegrityError as exc:
        # L'index unique partiel ux_client_user_ips_active_ip a tranché une
        # course entre deux requêtes.
        await db.rollback()
        raise IpTaken(normalized or "") from exc

    # Rattacher les logs ORPHELINS de cette IP au poste. Les logs déjà rattachés
    # gardent leur poste d'origine : c'est exactement ce qui permet de savoir à
    # qui appartenait l'IP au moment de la requête.
    logs_linked = 0
    if normalized is not None:
        res = await db.execute(
            update(AccessLog)
            .where(AccessLog.client_ip == normalized, AccessLog.client_user_id.is_(None))
            .values(client_user_id=locked.id)
        )
        logs_linked = res.rowcount or 0

    user.ip_address = normalized
    return IpChangeResult(
        changed=True,
        previous_ip=previous_ip,
        new_ip=normalized,
        released_from=released_from,
        logs_linked=logs_linked,
    )


async def release_client_user_ip(
    db: AsyncSession, user: ClientUser, source: str = "manual", note: str | None = None
) -> IpChangeResult:
    """Prive le poste de son IP, en clôturant sa période courante."""
    return await change_client_user_ip(db, user, None, source=source, note=note)


async def ip_history(db: AsyncSession, user_id: int) -> list[ClientUserIp]:
    """Périodes de détention d'un poste, de la plus récente à la plus ancienne."""
    return list((await db.execute(
        select(ClientUserIp)
        .where(ClientUserIp.user_id == user_id)
        .order_by(ClientUserIp.assigned_at.desc(), ClientUserIp.id.desc())
    )).scalars().all())


async def owner_at(db: AsyncSession, ip: str, when: datetime) -> int | None:
    """Quel poste détenait cette IP à cet instant ? (audit)"""
    return (await db.execute(
        select(ClientUserIp.user_id)
        .where(
            ClientUserIp.ip_address == ip,
            ClientUserIp.assigned_at <= when,
            (ClientUserIp.released_at.is_(None)) | (ClientUserIp.released_at > when),
        )
        .order_by(ClientUserIp.assigned_at.desc())
        .limit(1)
    )).scalar_one_or_none()
