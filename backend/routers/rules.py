import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, field_validator
from typing import Optional

from database import get_db
from models   import FilterRule
from security import require_permission
from models   import User

router = APIRouter()


# ── Protection ReDoS ─────────────────────────────────────────────────────────

_REGEX_MAX_LENGTH = 500  # longueur max du pattern

# Détection statique de patterns dangereux (backtracking catastrophique)
# Quantificateurs imbriqués : (a+)+, (a*)+, (a+)*, (a{2,})+ etc.
_DANGEROUS_PATTERNS = [
    re.compile(r'\([^)]*[+*][^)]*\)[+*]'),     # (x+)+ (x+)* (x*)+ (x*)*
    re.compile(r'\([^)]*\{[^}]+\}[^)]*\)[+*]'), # (x{n,})+ etc.
    re.compile(r'[+*]\??\.\*[+*]'),              # a+.*b+ adjacents
]


def _has_dangerous_pattern(pattern: str) -> bool:
    """Détecte les constructions regex connues pour causer du backtracking catastrophique."""
    for dp in _DANGEROUS_PATTERNS:
        if dp.search(pattern):
            return True
    return False


def _safe_regex_test(pattern: str) -> None:
    """Compile la regex et vérifie qu'elle ne contient pas de patterns dangereux."""
    if len(pattern) > _REGEX_MAX_LENGTH:
        raise ValueError(f"Le pattern ne doit pas dépasser {_REGEX_MAX_LENGTH} caractères")
    if _has_dangerous_pattern(pattern):
        raise ValueError(
            "Expression régulière rejetée : quantificateurs imbriqués détectés "
            "(risque de backtracking catastrophique). "
            "Exemple interdit : (a+)+, (.*a)* — simplifiez votre expression."
        )
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Expression régulière invalide : {e}")


def safe_regex_search(pattern: str, text: str) -> bool:
    """Exécute re.search de façon sécurisée (le pattern a déjà été validé à la création)."""
    try:
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        return False


# ── Schémas ───────────────────────────────────────────────────────────────────

class RuleIn(BaseModel):
    pattern:     str
    action:      str
    description: Optional[str] = None
    priority:    int = 100
    enabled:     bool = True

    @field_validator("pattern")
    @classmethod
    def validate_regex(cls, v: str) -> str:
        _safe_regex_test(v)
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("block", "allow"):
            raise ValueError("action doit être 'block' ou 'allow'")
        return v


class RuleOut(BaseModel):
    id:          int
    pattern:     str
    action:      str
    description: Optional[str]
    priority:    int
    enabled:     bool
    created_at:  str
    updated_at:  str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_rule(cls, r: FilterRule) -> "RuleOut":
        return cls(
            id=r.id,
            pattern=r.pattern,
            action=r.action,
            description=r.description,
            priority=r.priority,
            enabled=r.enabled,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )


class RulesListResponse(BaseModel):
    items: list[RuleOut]
    total: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=RulesListResponse)
async def list_rules(
    skip:    int = Query(0, ge=0),
    limit:   int = Query(100, ge=1, le=500),
    search:  str = "",
    db:      AsyncSession = Depends(get_db),
    _user:   User = Depends(require_permission("rules.read")),
):
    q = select(FilterRule)
    if search:
        q = q.where(FilterRule.pattern.ilike(f"%{search}%"))
    q = q.order_by(FilterRule.priority.asc(), FilterRule.id.asc())

    total_q = select(func.count()).select_from(q.subquery())
    total   = (await db.execute(total_q)).scalar_one()

    result  = await db.execute(q.offset(skip).limit(limit))
    rules   = result.scalars().all()
    return RulesListResponse(items=[RuleOut.from_orm_rule(r) for r in rules], total=total)


@router.post("", response_model=RuleOut, status_code=201)
async def create_rule(
    body:  RuleIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("rules.write")),
):
    rule = FilterRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return RuleOut.from_orm_rule(rule)


@router.put("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: int,
    body:    RuleIn,
    db:      AsyncSession = Depends(get_db),
    _user:   User = Depends(require_permission("rules.write")),
):
    result = await db.execute(select(FilterRule).where(FilterRule.id == rule_id))
    rule   = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Règle introuvable")

    for field, value in body.model_dump().items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return RuleOut.from_orm_rule(rule)


@router.patch("/{rule_id}/toggle", response_model=RuleOut)
async def toggle_rule(
    rule_id: int,
    db:      AsyncSession = Depends(get_db),
    _user:   User = Depends(require_permission("rules.write")),
):
    result = await db.execute(select(FilterRule).where(FilterRule.id == rule_id))
    rule   = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Règle introuvable")
    rule.enabled = not rule.enabled
    await db.commit()
    await db.refresh(rule)
    return RuleOut.from_orm_rule(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: int,
    db:      AsyncSession = Depends(get_db),
    _user:   User = Depends(require_permission("rules.write")),
):
    result = await db.execute(select(FilterRule).where(FilterRule.id == rule_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Règle introuvable")
    await db.execute(delete(FilterRule).where(FilterRule.id == rule_id))
    await db.commit()
