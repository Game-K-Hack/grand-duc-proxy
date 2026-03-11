from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models   import TlsBypass
from security import get_current_user, require_admin
from models   import User

router = APIRouter()


class TlsBypassIn(BaseModel):
    host:        str
    description: Optional[str] = None


class TlsBypassOut(BaseModel):
    id:          int
    host:        str
    description: Optional[str]
    created_at:  str


@router.get("", response_model=list[TlsBypassOut])
async def list_bypass(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = (await db.execute(select(TlsBypass).order_by(TlsBypass.host))).scalars().all()
    return [
        TlsBypassOut(id=r.id, host=r.host, description=r.description, created_at=r.created_at.isoformat())
        for r in rows
    ]


@router.post("", response_model=TlsBypassOut, status_code=201)
async def create_bypass(
    body:  TlsBypassIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    host = body.host.strip().lower().lstrip("*.")
    if not host:
        raise HTTPException(400, "Hôte invalide")
    if (await db.execute(select(TlsBypass).where(TlsBypass.host == host))).scalar_one_or_none():
        raise HTTPException(409, "Cet hôte est déjà dans la liste de bypass")
    row = TlsBypass(host=host, description=body.description)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return TlsBypassOut(id=row.id, host=row.host, description=row.description, created_at=row.created_at.isoformat())


@router.delete("/{bypass_id}", status_code=204)
async def delete_bypass(
    bypass_id: int,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    if not (await db.execute(select(TlsBypass).where(TlsBypass.id == bypass_id))).scalar_one_or_none():
        raise HTTPException(404, "Entrée introuvable")
    await db.execute(delete(TlsBypass).where(TlsBypass.id == bypass_id))
    await db.commit()
