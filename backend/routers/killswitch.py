from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models   import AppSetting, KillswitchHistory, User
from security import require_permission, verify_password

router = APIRouter()


class KillswitchOut(BaseModel):
    active: bool


class KillswitchIn(BaseModel):
    active: bool


class HistoryEntryOut(BaseModel):
    id:         int
    action:     str
    username:   str
    created_at: datetime


class VerifyPasswordIn(BaseModel):
    password: str


@router.get("", response_model=KillswitchOut)
async def get_killswitch(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("killswitch.read")),
):
    row = await db.get(AppSetting, "killswitch")
    return KillswitchOut(active=row.value == "true" if row else False)


@router.post("", response_model=KillswitchOut)
async def set_killswitch(
    body: KillswitchIn,
    db:   AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("killswitch.write")),
):
    row = await db.get(AppSetting, "killswitch")
    if row:
        row.value = "true" if body.active else "false"
    else:
        db.add(AppSetting(key="killswitch", value="true" if body.active else "false"))

    action = "activated" if body.active else "deactivated"
    db.add(KillswitchHistory(action=action, username=user.username))
    await db.commit()

    import asyncio
    from services.email import notify
    label = "activé" if body.active else "désactivé"
    asyncio.create_task(notify(
        "killswitch",
        f"Killswitch {label}",
        [f"Action : <strong>{label}</strong>", f"Par : {user.username}"],
    ))

    return KillswitchOut(active=body.active)


@router.get("/history", response_model=list[HistoryEntryOut])
async def get_history(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("killswitch.read")),
):
    result = await db.execute(
        select(KillswitchHistory).order_by(KillswitchHistory.created_at.desc()).limit(50)
    )
    return result.scalars().all()


@router.post("/verify-password", status_code=204)
async def verify_password_endpoint(
    body: VerifyPasswordIn,
    db:   AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("killswitch.write")),
):
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe incorrect",
        )
