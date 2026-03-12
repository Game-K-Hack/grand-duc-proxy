from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
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
    __table_args__ = (
        Index("ix_access_logs_accessed_at", "accessed_at"),
        Index("ix_access_logs_blocked_accessed_at", "blocked", "accessed_at"),
        Index("ix_access_logs_client_ip", "client_ip"),
        Index("ix_access_logs_host", "host"),
    )

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
    role_id:         Mapped[int | None] = mapped_column(BigInteger, ForeignKey("roles.id"))
    enabled:         Mapped[bool]       = mapped_column(Boolean, default=True)
    created_at:      Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class UserTheme(Base):
    """Préférences de thème par utilisateur (table séparée pour éviter ALTER sur users)."""
    __tablename__ = "user_themes"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme:   Mapped[str] = mapped_column(Text, nullable=False, default="{}")

class Role(Base):
    __tablename__ = "roles"
    id:          Mapped[int]        = mapped_column(BigInteger, primary_key=True)
    name:        Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    permissions: Mapped[str]        = mapped_column(Text, default="{}")
    is_builtin:  Mapped[bool]       = mapped_column(Boolean, default=False)
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientGroup(Base):
    __tablename__ = "client_groups"
    id:          Mapped[int]        = mapped_column(BigInteger, primary_key=True)
    name:        Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_default:  Mapped[bool]       = mapped_column(Boolean, default=False, nullable=False)
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())


class RmmIntegration(Base):
    """Intégration RMM externe (Tactical RMM, NinjaRMM, Datto, Atera…)."""
    __tablename__ = "rmm_integrations"
    id:                    Mapped[int]         = mapped_column(BigInteger, primary_key=True)
    name:                  Mapped[str]         = mapped_column(Text, nullable=False)
    type:                  Mapped[str]         = mapped_column(String(30), nullable=False)
    url:                   Mapped[str]         = mapped_column(Text, nullable=False)
    api_key:               Mapped[str]         = mapped_column(Text, nullable=False)
    api_secret:            Mapped[str | None]  = mapped_column(Text)
    enabled:               Mapped[bool]        = mapped_column(Boolean, default=True)
    sync_interval_minutes: Mapped[int]         = mapped_column(Integer, default=60)
    auto_group_by:         Mapped[str]         = mapped_column(String(20), default="none")  # none|client|site|client_site
    last_sync_at:          Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status:      Mapped[str | None]  = mapped_column(Text)
    created_at:            Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientUser(Base):
    __tablename__ = "client_users"
    id:                  Mapped[int]         = mapped_column(BigInteger, primary_key=True)
    ip_address:          Mapped[str]         = mapped_column(Text, unique=True, nullable=False)
    label:               Mapped[str | None]  = mapped_column(Text)
    hostname:            Mapped[str | None]  = mapped_column(Text)
    os:                  Mapped[str | None]  = mapped_column(Text)
    logged_user:         Mapped[str | None]  = mapped_column(Text)
    source:              Mapped[str]         = mapped_column(String(20), default='manual')
    rmm_agent_id:        Mapped[str | None]  = mapped_column(Text)
    last_seen_rmm:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rmm_integration_id:  Mapped[int | None]  = mapped_column(BigInteger, ForeignKey("rmm_integrations.id", ondelete="SET NULL"))
    created_at:          Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())


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


class NotificationPref(Base):
    """Préférences de notification par utilisateur et type d'événement."""
    __tablename__ = "notification_prefs"
    user_id:    Mapped[int]  = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    event_type: Mapped[str]  = mapped_column(Text, primary_key=True)
    enabled:    Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationRuleWatch(Base):
    """Règles à surveiller pour déclencher des alertes sur les logs d'accès."""
    __tablename__ = "notification_rule_watches"
    user_id:              Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id",        ondelete="CASCADE"), primary_key=True)
    rule_id:              Mapped[int] = mapped_column(BigInteger, ForeignKey("filter_rules.id", ondelete="CASCADE"), primary_key=True)
    last_notified_log_id: Mapped[int] = mapped_column(BigInteger, default=0)


class KillswitchHistory(Base):
    """Historique des activations/désactivations du killswitch."""
    __tablename__ = "killswitch_history"
    id:         Mapped[int]      = mapped_column(BigInteger, primary_key=True)
    action:     Mapped[str]      = mapped_column(Text, nullable=False)   # 'activated' | 'deactivated'
    username:   Mapped[str]      = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CertificateHistory(Base):
    """Historique des générations/imports de certificat CA."""
    __tablename__ = "certificate_history"
    id:          Mapped[int]            = mapped_column(BigInteger, primary_key=True)
    action:      Mapped[str]            = mapped_column(Text, nullable=False)  # 'generated' | 'imported'
    username:    Mapped[str]            = mapped_column(Text, nullable=False)
    subject:     Mapped[str | None]     = mapped_column(Text)
    fingerprint: Mapped[str | None]     = mapped_column(Text)
    not_before:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    not_after:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:  Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
