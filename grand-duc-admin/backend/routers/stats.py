from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Literal

from database import get_db
from models   import AccessLog, FilterRule
from security import require_permission
from models   import User

router = APIRouter()


class TopDomain(BaseModel):
    host:    str | None
    count:   int
    blocked: int


# ── Trafic réseau ─────────────────────────────────────────────────────────────

class TrafficPoint(BaseModel):
    label:   str   # heure ou minute selon le mode
    total:   int
    blocked: int
    allowed: int


class TrafficResponse(BaseModel):
    points: list[TrafficPoint]
    mode:   str   # "24h" | "1h"


@router.get("/traffic", response_model=TrafficResponse)
async def get_traffic(
    mode:  Literal["24h", "1h"] = Query("24h"),
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("dashboard.read")),
):
    """
    Retourne les données de trafic agrégées :
    - mode=24h : 24 points, un par heure sur les dernières 24h
    - mode=1h  : 60 points, un par minute sur la dernière heure
    """
    if mode == "24h":
        # Agrégation par heure — génère une série complète même si certaines
        # heures ont 0 requêtes (via generate_series)
        sql = text("""
            WITH hours AS (
                SELECT generate_series(
                    date_trunc('hour', NOW()) - INTERVAL '23 hours',
                    date_trunc('hour', NOW()),
                    INTERVAL '1 hour'
                ) AS slot
            )
            SELECT
                TO_CHAR(h.slot, 'HH24:MI') AS label,
                COALESCE(COUNT(l.id), 0)                              AS total,
                COALESCE(SUM(CASE WHEN l.blocked THEN 1 ELSE 0 END), 0) AS blocked
            FROM hours h
            LEFT JOIN access_logs l
                ON date_trunc('hour', l.accessed_at) = h.slot
            GROUP BY h.slot
            ORDER BY h.slot ASC
        """)
    else:
        # Agrégation par minute sur la dernière heure
        sql = text("""
            WITH minutes AS (
                SELECT generate_series(
                    date_trunc('minute', NOW()) - INTERVAL '59 minutes',
                    date_trunc('minute', NOW()),
                    INTERVAL '1 minute'
                ) AS slot
            )
            SELECT
                TO_CHAR(m.slot, 'HH24:MI') AS label,
                COALESCE(COUNT(l.id), 0)                              AS total,
                COALESCE(SUM(CASE WHEN l.blocked THEN 1 ELSE 0 END), 0) AS blocked
            FROM minutes m
            LEFT JOIN access_logs l
                ON date_trunc('minute', l.accessed_at) = m.slot
            GROUP BY m.slot
            ORDER BY m.slot ASC
        """)

    rows = (await db.execute(sql)).all()
    points = [
        TrafficPoint(
            label=r.label,
            total=int(r.total),
            blocked=int(r.blocked),
            allowed=int(r.total) - int(r.blocked),
        )
        for r in rows
    ]
    return TrafficResponse(points=points, mode=mode)


class StatsResponse(BaseModel):
    total_requests:    int
    blocked_requests:  int
    allowed_requests:  int
    active_rules:      int
    top_blocked:       list[TopDomain]
    top_domains:       list[TopDomain]
    requests_today:    int
    block_rate:        float          # 0.0 – 100.0


@router.get("", response_model=StatsResponse)
async def get_stats(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("dashboard.read")),
):
    # Combiné : totaux + bloqués + aujourd'hui en 1 requête (au lieu de 3)
    counts_row = (await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(AccessLog.blocked == True).label("blocked"),
            func.count().filter(
                func.date(AccessLog.accessed_at) == func.current_date()
            ).label("today"),
        ).select_from(AccessLog)
    )).one()
    total, blocked, requests_today = counts_row.total, counts_row.blocked, counts_row.today
    allowed = total - blocked

    # Règles actives
    active_rules = (await db.execute(
        select(func.count()).where(FilterRule.enabled == True)
    )).scalar_one()

    # Top 10 domaines bloqués
    top_blocked_rows = (await db.execute(
        select(AccessLog.host, func.count().label("count"))
        .where(AccessLog.blocked == True)
        .group_by(AccessLog.host)
        .order_by(func.count().desc())
        .limit(10)
    )).all()

    # Top 10 domaines toutes requêtes confondues
    top_domains_rows = (await db.execute(
        select(
            AccessLog.host,
            func.count().label("count"),
            func.count().filter(AccessLog.blocked == True).label("blocked"),
        )
        .group_by(AccessLog.host)
        .order_by(func.count().desc())
        .limit(10)
    )).all()

    block_rate = round((blocked / total * 100) if total > 0 else 0.0, 1)

    return StatsResponse(
        total_requests=total,
        blocked_requests=blocked,
        allowed_requests=allowed,
        active_rules=active_rules,
        top_blocked=[TopDomain(host=r.host, count=r.count, blocked=r.count) for r in top_blocked_rows],
        top_domains=[TopDomain(host=r.host, count=r.count, blocked=r.blocked or 0) for r in top_domains_rows],
        requests_today=requests_today,
        block_rate=block_rate,
    )