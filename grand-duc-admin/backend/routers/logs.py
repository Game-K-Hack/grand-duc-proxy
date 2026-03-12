from fastapi import APIRouter, Depends
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models   import AccessLog, ClientUser
from security import require_permission
from models   import User

router = APIRouter()


class LogOut(BaseModel):
    id:           int
    client_ip:    Optional[str]
    client_label: Optional[str]
    host:         Optional[str]
    url:          str
    method:       str
    blocked:      bool
    user_agent:   Optional[str]
    accessed_at:  str


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
    _user:   User = Depends(require_permission("logs.read")),
):
    q = (
        select(AccessLog, ClientUser.label.label("client_label"))
        .outerjoin(ClientUser, AccessLog.client_ip == ClientUser.ip_address)
    )

    if search:
        q = q.where(or_(
            AccessLog.host.ilike(f"%{search}%"),
            AccessLog.url.ilike(f"%{search}%"),
            AccessLog.client_ip.ilike(f"%{search}%"),
            ClientUser.label.ilike(f"%{search}%"),
        ))
    if blocked is not None:
        q = q.where(AccessLog.blocked == blocked)

    q = q.order_by(AccessLog.accessed_at.desc())

    total_q = select(func.count()).select_from(q.subquery())
    total   = (await db.execute(total_q)).scalar_one()

    result = await db.execute(q.offset(skip).limit(limit))
    rows   = result.all()

    return LogsListResponse(
        items=[
            LogOut(
                id=row.AccessLog.id,
                client_ip=row.AccessLog.client_ip,
                client_label=row.client_label,
                host=row.AccessLog.host,
                url=row.AccessLog.url,
                method=row.AccessLog.method,
                blocked=row.AccessLog.blocked,
                user_agent=row.AccessLog.user_agent,
                accessed_at=row.AccessLog.accessed_at.isoformat(),
            )
            for row in rows
        ],
        total=total,
    )
