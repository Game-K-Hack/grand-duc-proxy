from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models   import AccessLog, FilterRule
from security import get_current_user
from models   import User

router = APIRouter()


class TopDomain(BaseModel):
    host:    str
    count:   int
    blocked: int


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
    _user: User = Depends(get_current_user),
):
    # Totaux
    total   = (await db.execute(select(func.count()).select_from(AccessLog))).scalar_one()
    blocked = (await db.execute(
        select(func.count()).where(AccessLog.blocked == True)
    )).scalar_one()
    allowed = total - blocked

    # Règles actives
    active_rules = (await db.execute(
        select(func.count()).where(FilterRule.enabled == True)
    )).scalar_one()

    # Requêtes aujourd'hui
    today_q = select(func.count()).where(
        func.date(AccessLog.accessed_at) == func.current_date()
    )
    requests_today = (await db.execute(today_q)).scalar_one()

    # Top 10 domaines bloqués
    top_blocked_q = (
        select(
            AccessLog.host,
            func.count().label("count"),
            func.sum(func.cast(AccessLog.blocked, type_=func.count().type)).label("blocked"),
        )
        .where(AccessLog.blocked == True)
        .group_by(AccessLog.host)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_blocked_rows = (await db.execute(top_blocked_q)).all()

    # Top 10 domaines toutes requêtes confondues
    top_domains_q = (
        select(
            AccessLog.host,
            func.count().label("count"),
            func.count().filter(AccessLog.blocked == True).label("blocked"),
        )
        .group_by(AccessLog.host)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_domains_rows = (await db.execute(top_domains_q)).all()

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
