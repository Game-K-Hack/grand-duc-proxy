from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class FilterRule(Base):
    __tablename__ = "filter_rules"

    id:          Mapped[int]           = mapped_column(BigInteger, primary_key=True)
    pattern:     Mapped[str]           = mapped_column(Text, nullable=False)
    action:      Mapped[str]           = mapped_column(String(10), nullable=False)
    description: Mapped[str | None]    = mapped_column(Text)
    priority:    Mapped[int]           = mapped_column(Integer, default=100)
    enabled:     Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at:  Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:  Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AccessLog(Base):
    __tablename__ = "access_logs"

    id:          Mapped[int]           = mapped_column(BigInteger, primary_key=True)
    client_ip:   Mapped[str | None]    = mapped_column(Text)
    host:        Mapped[str]           = mapped_column(Text, nullable=False)
    url:         Mapped[str]           = mapped_column(Text, nullable=False)
    method:      Mapped[str]           = mapped_column(String(10), default="CONNECT")
    blocked:     Mapped[bool]          = mapped_column(Boolean, nullable=False)
    user_agent:  Mapped[str | None]    = mapped_column(Text)
    accessed_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id:              Mapped[int]        = mapped_column(BigInteger, primary_key=True)
    username:        Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    email:           Mapped[str | None] = mapped_column(Text)
    hashed_password: Mapped[str]        = mapped_column(Text, nullable=False)
    role:            Mapped[str]        = mapped_column(String(10), default="viewer")
    enabled:         Mapped[bool]       = mapped_column(Boolean, default=True)
    created_at:      Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class ClientGroup(Base):
    __tablename__ = "client_groups"
    id:          Mapped[int]        = mapped_column(BigInteger, primary_key=True)
    name:        Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_default:  Mapped[bool]       = mapped_column(Boolean, default=False, nullable=False)
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientUser(Base):
    __tablename__ = "client_users"
    id:         Mapped[int]        = mapped_column(BigInteger, primary_key=True)
    ip_address: Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    label:      Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientUserGroups(Base):
    """Table de jonction many-to-many utilisateurs ↔ groupes."""
    __tablename__ = "client_user_groups"
    user_id:  Mapped[int] = mapped_column(BigInteger, ForeignKey("client_users.id",  ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("client_groups.id", ondelete="CASCADE"), primary_key=True)


class GroupRule(Base):
    """Association règle ↔ groupe avec action spécifique au groupe."""
    __tablename__ = "group_rules"
    id:        Mapped[int]      = mapped_column(BigInteger, primary_key=True)
    group_id:  Mapped[int]      = mapped_column(BigInteger, ForeignKey("client_groups.id", ondelete="CASCADE"), nullable=False)
    rule_id:   Mapped[int]      = mapped_column(BigInteger, ForeignKey("filter_rules.id",  ondelete="CASCADE"), nullable=False)
    action:    Mapped[str]      = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TlsBypass(Base):
    """Hôtes exemptés du filtrage proxy (sous-domaines inclus)."""
    __tablename__ = "tls_bypass"
    id:          Mapped[int]        = mapped_column(BigInteger, primary_key=True)
    host:        Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppSetting(Base):
    """Paramètres globaux de l'application (clé/valeur)."""
    __tablename__ = "app_settings"
    key:   Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
