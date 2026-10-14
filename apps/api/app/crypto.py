"""Cifra do texto original por tenant (opcional). Chave derivada de uma chave mestra via HKDF.

Interino: a chave mestra vem de variável de ambiente. A Etapa 9 troca por chave por tenant em KMS.
"""
from __future__ import annotations

import base64
import uuid

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings


class MasterKeyMissingError(RuntimeError):
    pass


def _fernet(tenant_id: uuid.UUID) -> Fernet:
    if not settings.original_text_master_key:
        raise MasterKeyMissingError("ORIGINAL_TEXT_MASTER_KEY não configurada")
    master = base64.urlsafe_b64decode(settings.original_text_master_key)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"promptshield/original/" + tenant_id.bytes).derive(master)
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_original(tenant_id: uuid.UUID, text: str) -> bytes:
    return _fernet(tenant_id).encrypt(text.encode("utf-8"))


def decrypt_original(tenant_id: uuid.UUID, blob: bytes) -> str:
    return _fernet(tenant_id).decrypt(blob).decode("utf-8")
