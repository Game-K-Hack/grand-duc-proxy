from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
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
