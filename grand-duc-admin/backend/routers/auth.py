import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models   import User
from security import verify_password, hash_password, create_access_token, get_current_user, load_user_permissions

router = APIRouter()


# ── Rate limiting simple (en mémoire) ────────────────────────────────────────
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5          # tentatives max
_WINDOW_SECONDS = 300      # fenêtre de 5 minutes
_LOCKOUT_SECONDS = 900     # lockout de 15 minutes après dépassement

# Hash factice pour le timing constant (pré-calculé au démarrage)
_DUMMY_HASH = hash_password("dummy_password_for_timing")


def _check_rate_limit(ip: str):
    """Vérifie et applique le rate limiting par IP."""
    now = time.time()
    attempts = _LOGIN_ATTEMPTS[ip]
    # Nettoyer les tentatives expirées
    _LOGIN_ATTEMPTS[ip] = [t for t in attempts if now - t < _LOCKOUT_SECONDS]
    attempts = _LOGIN_ATTEMPTS[ip]
    if len(attempts) >= _MAX_ATTEMPTS:
        oldest = attempts[0]
        remaining = int(_LOCKOUT_SECONDS - (now - oldest))
        mins = round(remaining / 60)
        if mins >= 2:
            time_str = f"{mins} minutes"
        elif remaining >= 60:
            time_str = "1 minute"
        else:
            time_str = f"{remaining} secondes"
        raise HTTPException(
            status_code=429,
            detail=f"Trop de tentatives. Réessayez dans {time_str}.",
        )


def _record_attempt(ip: str):
    _LOGIN_ATTEMPTS[ip].append(time.time())


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    username:     str
    role:         str


class MeResponse(BaseModel):
    id:          int
    username:    str
    email:       str | None
    role:        str
    role_id:     int | None = None
    permissions: dict[str, bool] = {}


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form:    OAuth2PasswordRequestForm = Depends(),
    db:      AsyncSession              = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    result = await db.execute(select(User).where(User.username == form.username))
    user   = result.scalar_one_or_none()

    # Timing constant : toujours vérifier un hash même si l'utilisateur n'existe pas
    if not user:
        verify_password(form.password, _DUMMY_HASH)
        _record_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
        )

    if not user.enabled or not verify_password(form.password, user.hashed_password):
        _record_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
        )

    # Mise à jour last_login
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login=datetime.now(timezone.utc))
    )
    await db.commit()

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, username=user.username, role=user.role)


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    perms = await load_user_permissions(current_user, db)
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        role_id=current_user.role_id,
        permissions=perms,
    )
