from datetime import datetime, timedelta, timezone
from typing import Optional
import json

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config   import settings
from database import get_db
from models   import User, Role

pwd_context    = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme  = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire    = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db:    AsyncSession = Depends(get_db),
) -> User:
    return await _decode_user(token, db)


async def get_current_user_query(
    token: str = Query(...),
    db:    AsyncSession = Depends(get_db),
) -> User:
    """Variante de get_current_user pour EventSource (token en query param)."""
    return await _decode_user(token, db)


async def _decode_user(token: str, db: AsyncSession) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
    )
    try:
        payload  = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    result = await db.execute(select(User).where(User.username == username))
    user   = result.scalar_one_or_none()
    if user is None or not user.enabled:
        raise credentials_exception
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Droits administrateur requis")
    return current_user


# ── Permissions granulaires ──────────────────────────────────────────────────

async def load_user_permissions(user: User, db: AsyncSession) -> dict[str, bool]:
    """Charge les permissions du rôle de l'utilisateur (avec cache requête)."""
    if hasattr(user, "_perms_cache"):
        return user._perms_cache
    perms: dict[str, bool] = {}
    if user.role_id:
        result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = result.scalar_one_or_none()
        if role:
            perms = json.loads(role.permissions)
    user._perms_cache = perms
    return perms


def require_permission(*perm_keys: str):
    """Factory : renvoie une dépendance FastAPI vérifiant les permissions."""
    async def _check(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        perms = await load_user_permissions(current_user, db)
        for key in perm_keys:
            if not perms.get(key):
                raise HTTPException(status_code=403, detail="Permission insuffisante")
        return current_user
    return _check


def require_permission_query(*perm_keys: str):
    """Variante pour les endpoints SSE (token en query param)."""
    async def _check(
        token: str = Query(...),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        user = await _decode_user(token, db)
        perms = await load_user_permissions(user, db)
        for key in perm_keys:
            if not perms.get(key):
                raise HTTPException(status_code=403, detail="Permission insuffisante")
        return user
    return _check
