from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models   import AccessLog, ClientUser
from security import require_permission
from models   import User

router = APIRouter()


class LogOut(BaseModel):
    id:              int
    client_ip:       Optional[str]
    client_user_id:  Optional[int]
    # False = poste seulement déduit de l'IP courante (log antérieur au suivi
    # des IP tournantes), et non figé au moment de la requête.
    client_resolved: bool
    client_label:    Optional[str]
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
    skip:    int = Query(0, ge=0),
    limit:   int = Query(50, ge=1, le=500),
    search:  str = "",
    blocked: Optional[bool] = None,
    client_user_id: Optional[int] = None,
    db:      AsyncSession = Depends(get_db),
    _user:   User = Depends(require_permission("logs.read")),
):
    # Deux résolutions du poste : la référence figée par le proxy au moment de
    # la requête (fiable même après un changement d'IP), et un repli par IP
    # courante pour les logs écrits avant la mise en place du suivi.
    cu_direct = aliased(ClientUser)
    cu_ip     = aliased(ClientUser)
    label = func.coalesce(
        cu_direct.label, cu_direct.hostname, cu_ip.label, cu_ip.hostname
    ).label("client_label")

    q = (
        select(AccessLog, label)
        .outerjoin(cu_direct, AccessLog.client_user_id == cu_direct.id)
        .outerjoin(cu_ip, AccessLog.client_ip == cu_ip.ip_address)
    )

    if search:
        q = q.where(or_(
            AccessLog.host.ilike(f"%{search}%"),
            AccessLog.url.ilike(f"%{search}%"),
            AccessLog.client_ip.ilike(f"%{search}%"),
            cu_direct.label.ilike(f"%{search}%"),
            cu_ip.label.ilike(f"%{search}%"),
        ))
    if blocked is not None:
        q = q.where(AccessLog.blocked == blocked)
    if client_user_id is not None:
        # « Tous les accès de ce poste », toutes ses IP successives confondues.
        q = q.where(AccessLog.client_user_id == client_user_id)

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
                client_user_id=row.AccessLog.client_user_id,
                client_resolved=row.AccessLog.client_user_id is not None,
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
