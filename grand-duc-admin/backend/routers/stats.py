import time
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Literal

from database import get_db
from models   import AccessLog, AppSetting, FilterRule, ClientUser
from security import require_permission
from models   import User

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Cache mémoire simple ─────────────────────────────────────────────────────
_cache: dict[str, tuple[float, dict]] = {}  # clé → (timestamp, données)
_STATS_TTL = 10      # secondes — les stats sont cachées 10s
_TRAFFIC_TTL = 15    # secondes — le trafic est caché 15s


def _get_cached(key: str, ttl: float):
    entry = _cache.get(key)
    if entry and time.time() - entry[0] < ttl:
        return entry[1]
    return None


def _set_cached(key: str, data):
    _cache[key] = (time.time(), data)


class TopDomain(BaseModel):
    host:    str | None
    count:   int
    blocked: int


class TopClient(BaseModel):
    ip:      str
    label:   str | None
    total:   int
    blocked: int


# ── Trafic réseau ─────────────────────────────────────────────────────────────

class TrafficPoint(BaseModel):
    label:   str
    total:   int
    blocked: int
    allowed: int


class TrafficResponse(BaseModel):
    points: list[TrafficPoint]
    mode:   str


@router.get("/traffic", response_model=TrafficResponse)
async def get_traffic(
    mode:  Literal["24h", "1h"] = Query("24h"),
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("dashboard.read")),
):
    cached = _get_cached(f"traffic_{mode}", _TRAFFIC_TTL)
    if cached:
        logger.info("[TRAFFIC] cache hit")
        return cached

    t0 = time.time()
    if mode == "24h":
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
    result = TrafficResponse(points=points, mode=mode)
    _set_cached(f"traffic_{mode}", result)
    logger.info("[TRAFFIC %s] requête SQL en %.0f ms", mode, (time.time() - t0) * 1000)
    return result


class StatsResponse(BaseModel):
    # Aujourd'hui
    requests_today:     int
    blocked_today:      int
    allowed_today:      int
    block_rate_today:   float
    active_clients:     int
    # Hier (comparaison)
    requests_yesterday: int
    blocked_yesterday:  int
    # Contexte
    active_rules:       int
    killswitch:         bool
    # Top listes (aujourd'hui)
    top_blocked:        list[TopDomain]
    top_domains:        list[TopDomain]
    top_clients:        list[TopClient]


@router.get("", response_model=StatsResponse)
async def get_stats(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("dashboard.read")),
):
    cached = _get_cached("stats", _STATS_TTL)
    if cached:
        logger.info("[STATS] cache hit")
        return cached

    t0 = time.time()
    # Aujourd'hui + hier en une seule requête
    counts_row = (await db.execute(
        select(
            func.count().filter(
                func.date(AccessLog.accessed_at) == func.current_date()
            ).label("today_total"),
            func.count().filter(
                func.date(AccessLog.accessed_at) == func.current_date(),
                AccessLog.blocked == True,
            ).label("today_blocked"),
            func.count(func.distinct(AccessLog.client_ip)).filter(
                func.date(AccessLog.accessed_at) == func.current_date()
            ).label("today_clients"),
            func.count().filter(
                func.date(AccessLog.accessed_at) == func.current_date() - 1
            ).label("yesterday_total"),
            func.count().filter(
                func.date(AccessLog.accessed_at) == func.current_date() - 1,
                AccessLog.blocked == True,
            ).label("yesterday_blocked"),
        ).select_from(AccessLog)
    )).one()

    today_total = counts_row.today_total
    today_blocked = counts_row.today_blocked
    today_allowed = today_total - today_blocked
    active_clients = counts_row.today_clients
    yesterday_total = counts_row.yesterday_total
    yesterday_blocked = counts_row.yesterday_blocked

    # Règles actives
    active_rules = (await db.execute(
        select(func.count()).where(FilterRule.enabled == True)
    )).scalar_one()

    # Top 10 domaines bloqués (aujourd'hui)
    top_blocked_rows = (await db.execute(
        select(AccessLog.host, func.count().label("count"))
        .where(
            AccessLog.blocked == True,
            func.date(AccessLog.accessed_at) == func.current_date(),
        )
        .group_by(AccessLog.host)
        .order_by(func.count().desc())
        .limit(10)
    )).all()

    # Top 10 domaines visités (aujourd'hui)
    top_domains_rows = (await db.execute(
        select(
            AccessLog.host,
            func.count().label("count"),
            func.count().filter(AccessLog.blocked == True).label("blocked"),
        )
        .where(func.date(AccessLog.accessed_at) == func.current_date())
        .group_by(AccessLog.host)
        .order_by(func.count().desc())
        .limit(10)
    )).all()

    # Top 10 clients actifs (aujourd'hui) avec label
    top_clients_rows = (await db.execute(
        select(
            AccessLog.client_ip,
            func.count().label("total"),
            func.count().filter(AccessLog.blocked == True).label("blocked"),
            ClientUser.label,
        )
        .outerjoin(ClientUser, AccessLog.client_ip == ClientUser.ip_address)
        .where(func.date(AccessLog.accessed_at) == func.current_date())
        .group_by(AccessLog.client_ip, ClientUser.label)
        .order_by(func.count().desc())
        .limit(10)
    )).all()

    block_rate = round((today_blocked / today_total * 100) if today_total > 0 else 0.0, 1)

    ks_row = await db.get(AppSetting, "killswitch")
    killswitch_active = ks_row.value == "true" if ks_row else False

    result = StatsResponse(
        requests_today=today_total,
        blocked_today=today_blocked,
        allowed_today=today_allowed,
        block_rate_today=block_rate,
        active_clients=active_clients,
        requests_yesterday=yesterday_total,
        blocked_yesterday=yesterday_blocked,
        active_rules=active_rules,
        killswitch=killswitch_active,
        top_blocked=[TopDomain(host=r.host, count=r.count, blocked=r.count) for r in top_blocked_rows],
        top_domains=[TopDomain(host=r.host, count=r.count, blocked=r.blocked or 0) for r in top_domains_rows],
        top_clients=[TopClient(ip=r.client_ip or "?", label=r.label, total=r.total, blocked=r.blocked or 0) for r in top_clients_rows],
    )
    _set_cached("stats", result)
    logger.info("[STATS] requête SQL en %.0f ms", (time.time() - t0) * 1000)
    return result
