from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models   import AppSetting
from security import get_current_user, require_admin
from models   import User

router = APIRouter()


class KillswitchOut(BaseModel):
    active: bool


class KillswitchIn(BaseModel):
    active: bool


@router.get("", response_model=KillswitchOut)
async def get_killswitch(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    row = await db.get(AppSetting, "killswitch")
    return KillswitchOut(active=row.value == "true" if row else False)


@router.post("", response_model=KillswitchOut)
async def set_killswitch(
    body:  KillswitchIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    row = await db.get(AppSetting, "killswitch")
    if row:
        row.value = "true" if body.active else "false"
    else:
        db.add(AppSetting(key="killswitch", value="true" if body.active else "false"))
    await db.commit()
    return KillswitchOut(active=body.active)
