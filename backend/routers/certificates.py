"""
Gestion du certificat CA du proxy Grand-Duc.

Fichiers sur disque (chemin configuré par CERT_DIR) :
  grand-duc-ca.key  → clé privée PKCS#8 DER (binaire, confidentiel)
  grand-duc-ca.crt  → certificat X.509 PEM   (à distribuer aux postes)

⚠️  Après tout changement de certificat, redémarrer le proxy Rust.
"""

import hashlib
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config   import settings
from database import get_db
from models   import CertificateHistory, User
from security import require_permission

router = APIRouter()

CERT_DIR  = Path(settings.CERT_DIR)
CERT_PATH = CERT_DIR / "grand-duc-ca.crt"
KEY_PATH  = CERT_DIR / "grand-duc-ca.key"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_cert() -> x509.Certificate | None:
    if not CERT_PATH.exists():
        return None
    pem = CERT_PATH.read_bytes()
    return x509.load_pem_x509_certificate(pem)


def _fingerprint(cert: x509.Certificate) -> str:
    return cert.fingerprint(hashes.SHA256()).hex()


def _cert_info(cert: x509.Certificate) -> dict:
    try:
        subject = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    except Exception:
        subject = str(cert.subject)
    return {
        "subject":     subject,
        "fingerprint": _fingerprint(cert),
        "not_before":  cert.not_valid_before_utc.isoformat(),
        "not_after":   cert.not_valid_after_utc.isoformat(),
        "days_left":   (cert.not_valid_after_utc - datetime.now(timezone.utc)).days,
        "is_expired":  cert.not_valid_after_utc < datetime.now(timezone.utc),
    }


def _validate_ca_cert_and_key(cert_pem: bytes, key_der: bytes) -> x509.Certificate:
    """Valide que cert_pem est une CA et que key_der est la clé correspondante."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem)
    except Exception:
        raise HTTPException(status_code=400, detail="Certificat PEM invalide")

    # Vérifier basic constraints CA=True
    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        if not bc.value.ca:
            raise HTTPException(status_code=400, detail="Le certificat n'est pas une CA (BasicConstraints CA=False)")
    except x509.ExtensionNotFound:
        raise HTTPException(status_code=400, detail="Le certificat n'a pas d'extension BasicConstraints")

    # Charger la clé privée (DER)
    try:
        private_key = serialization.load_der_private_key(key_der, password=None)
    except Exception:
        raise HTTPException(status_code=400, detail="Clé privée DER invalide")

    # Vérifier que la clé correspond au certificat (comparaison des clés publiques)
    cert_pub = cert.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    key_pub = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    if cert_pub != key_pub:
        raise HTTPException(status_code=400, detail="La clé privée ne correspond pas au certificat")

    return cert


# ── Endpoints ─────────────────────────────────────────────────────────────────

class CertInfoOut(BaseModel):
    subject:     str
    fingerprint: str
    not_before:  str
    not_after:   str
    days_left:   int
    is_expired:  bool
    exists:      bool


class HistoryEntryOut(BaseModel):
    id:          int
    action:      str
    username:    str
    subject:     str | None
    fingerprint: str | None
    not_before:  datetime | None
    not_after:   datetime | None
    created_at:  datetime


@router.get("/info", response_model=CertInfoOut)
async def get_cert_info(_user: User = Depends(require_permission("certificates.read"))):
    cert = _read_cert()
    if cert is None:
        return CertInfoOut(
            subject="", fingerprint="", not_before="", not_after="",
            days_left=0, is_expired=True, exists=False,
        )
    info = _cert_info(cert)
    return CertInfoOut(**info, exists=True)


@router.get("/ca.crt")  # Public — pas d'authentification
async def download_ca():
    if not CERT_PATH.exists():
        raise HTTPException(status_code=404, detail="Certificat CA introuvable")
    return FileResponse(
        path=str(CERT_PATH),
        media_type="application/x-x509-ca-cert",
        filename="grand-duc-ca.crt",
    )


@router.post("/generate", response_model=CertInfoOut)
async def generate_cert(
    db:   AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("certificates.write")),
):
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    # Génération clé ECDSA P-256 (même algo que rcgen par défaut)
    private_key = ec.generate_private_key(ec.SECP256R1())
    key_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Certificat CA auto-signé — 10 ans de validité
    now = datetime.now(timezone.utc)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME,       "Grand-Duc Proxy CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Grand-Duc"),
        x509.NameAttribute(NameOID.COUNTRY_NAME,      "FR"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()), critical=False)
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    KEY_PATH.write_bytes(key_der)
    CERT_PATH.write_bytes(cert_pem)

    info = _cert_info(cert)
    db.add(CertificateHistory(
        action="generated",
        username=user.username,
        subject=info["subject"],
        fingerprint=info["fingerprint"],
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
    ))
    await db.commit()

    import asyncio
    from services.email import notify
    asyncio.create_task(notify(
        "certificate",
        "Nouveau certificat CA généré",
        [f"Par : {user.username}", f"Sujet : {info['subject']}", f"Expire : {info['not_after']}"],
    ))

    return CertInfoOut(**info, exists=True)


@router.post("/import", response_model=CertInfoOut)
async def import_cert(
    cert_file: UploadFile = File(..., description="Certificat CA (.crt PEM)"),
    key_file:  UploadFile = File(..., description="Clé privée (.key PKCS#8 DER)"),
    db:        AsyncSession = Depends(get_db),
    user:      User = Depends(require_permission("certificates.write")),
):
    # Limite de taille : 1 Mo max par fichier (anti-DoS)
    MAX_UPLOAD = 1_048_576
    cert_pem = await cert_file.read(MAX_UPLOAD + 1)
    if len(cert_pem) > MAX_UPLOAD:
        raise HTTPException(400, "Le fichier certificat dépasse la taille maximale (1 Mo)")
    key_der = await key_file.read(MAX_UPLOAD + 1)
    if len(key_der) > MAX_UPLOAD:
        raise HTTPException(400, "Le fichier clé dépasse la taille maximale (1 Mo)")

    cert = _validate_ca_cert_and_key(cert_pem, key_der)

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    CERT_PATH.write_bytes(cert_pem)
    KEY_PATH.write_bytes(key_der)

    info = _cert_info(cert)
    db.add(CertificateHistory(
        action="imported",
        username=user.username,
        subject=info["subject"],
        fingerprint=info["fingerprint"],
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
    ))
    await db.commit()

    import asyncio
    from services.email import notify
    asyncio.create_task(notify(
        "certificate",
        "Certificat CA importé",
        [f"Par : {user.username}", f"Sujet : {info['subject']}", f"Expire : {info['not_after']}"],
    ))

    return CertInfoOut(**info, exists=True)


@router.get("/history", response_model=list[HistoryEntryOut])
async def get_history(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("certificates.read")),
):
    result = await db.execute(
        select(CertificateHistory)
        .order_by(CertificateHistory.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()
