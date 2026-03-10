from fastapi import APIRouter, Depends
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models   import AccessLog
from security import get_current_user
from models   import User

router = APIRouter()


class LogOut(BaseModel):
    id:          int
    client_ip:   Optional[str]
    host:        str
    url:         str
    method:      str
    blocked:     bool
    user_agent:  Optional[str]
    accessed_at: str


class LogsListResponse(BaseModel):
    items: list[LogOut]
    total: int


@router.get("", response_model=LogsListResponse)
async def list_logs(
    skip:    int = 0,
    limit:   int = 50,
    search:  str = "",
    blocked: Optional[bool] = None,
    db:      AsyncSession = Depends(get_db),
    _user:   User = Depends(get_current_user),
):
    q = select(AccessLog)

    if search:
        q = q.where(or_(
            AccessLog.host.ilike(f"%{search}%"),
            AccessLog.url.ilike(f"%{search}%"),
            AccessLog.client_ip.ilike(f"%{search}%"),
        ))
    if blocked is not None:
        q = q.where(AccessLog.blocked == blocked)

    q = q.order_by(AccessLog.accessed_at.desc())

    total_q = select(func.count()).select_from(q.subquery())
    total   = (await db.execute(total_q)).scalar_one()

    result  = await db.execute(q.offset(skip).limit(limit))
    logs    = result.scalars().all()

    return LogsListResponse(
        items=[
            LogOut(
                id=log.id,
                client_ip=log.client_ip,
                host=log.host,
                url=log.url,
                method=log.method,
                blocked=log.blocked,
                user_agent=log.user_agent,
                accessed_at=log.accessed_at.isoformat(),
            )
            for log in logs
        ],
        total=total,
    )
