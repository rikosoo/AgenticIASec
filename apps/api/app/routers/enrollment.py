"""Matrícula de dispositivos: o administrador cria um token (revogável, com validade e limite de usos); cada máquina troca o token por
uma chave de API PRÓPRIA. Assim um instalador vazado não permite falsificar eventos em nome da empresa por tempo indeterminado, e dá
para revogar uma máquina só. Integração REAL só depois de testada em máquinas reais (docs/implantacao-empresa.md)."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from app import audit, audit_system, ratelimit
from app.db import anonymous_session, tenant_session
from app.models import ApiKey, Device, EnrollmentToken
from app.security import READ_ROLES, Principal, generate_api_key, require_roles

router = APIRouter(prefix="/v1", tags=["matrícula de dispositivos"])
TOKEN_PREFIX = "pse_"  # noqa: S105 - prefixo público do formato do token, não é segredo


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class TokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    expires_in_days: int = Field(default=14, ge=1, le=90)
    max_uses: int | None = Field(default=1000, ge=1, le=100000)


class EnrollIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=10, max_length=200)
    hostname: str = Field(min_length=1, max_length=200)
    os: str | None = Field(default=None, max_length=60)
    client_version: str | None = Field(default=None, max_length=40)
    tools: list[str] = Field(default_factory=list, max_length=20)


@router.post("/enrollment-tokens", status_code=201, summary="Cria token de matrícula; o valor aparece só nesta resposta")
def create_token(body: TokenIn, p: Annotated[Principal, Depends(require_roles("admin"))]) -> dict:
    prefix = secrets.token_hex(4)
    token = f"{TOKEN_PREFIX}{prefix}_{secrets.token_urlsafe(24)}"
    with tenant_session(p.tenant_id) as s:
        t = EnrollmentToken(tenant_id=p.tenant_id, name=body.name, prefix=f"{TOKEN_PREFIX}{prefix}", token_hash=_hash(token),
                            expires_at=datetime.now(timezone.utc) + timedelta(days=body.expires_in_days), max_uses=body.max_uses)
        s.add(t)
        s.flush()
        audit.write(s, p, "enrollment_token.create", "enrollment_token", str(t.id),
                    {"name": body.name, "expires_in_days": body.expires_in_days, "max_uses": body.max_uses})
        return {"id": str(t.id), "name": t.name, "prefix": t.prefix, "token": token, "expires_at": t.expires_at.isoformat(), "max_uses": t.max_uses}


def _token_view(t: EnrollmentToken, now: datetime) -> dict:
    status_ = "revogado" if t.revoked_at else "expirado" if t.expires_at <= now else "esgotado" if t.max_uses is not None and t.uses >= t.max_uses else "ativo"
    return {"id": str(t.id), "name": t.name, "prefix": t.prefix, "status": status_, "uses": t.uses, "max_uses": t.max_uses,
            "expires_at": t.expires_at.isoformat(), "created_at": t.created_at.isoformat()}


@router.get("/enrollment-tokens")
def list_tokens(p: Annotated[Principal, Depends(require_roles("admin"))]) -> list[dict]:
    now = datetime.now(timezone.utc)
    with tenant_session(p.tenant_id) as s:
        return [_token_view(t, now) for t in s.scalars(select(EnrollmentToken).order_by(EnrollmentToken.created_at.desc()))]


@router.post("/enrollment-tokens/{token_id}/revoke")
def revoke_token(token_id: uuid.UUID, p: Annotated[Principal, Depends(require_roles("admin"))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        t = s.get(EnrollmentToken, token_id)
        if t is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "token não encontrado")
        t.revoked_at = t.revoked_at or datetime.now(timezone.utc)
        audit.write(s, p, "enrollment_token.revoke", "enrollment_token", str(t.id), {"name": t.name})
        return _token_view(t, datetime.now(timezone.utc))


@router.post("/enroll", status_code=201, summary="Troca um token de matrícula por uma chave de API própria da máquina (sem login)")
def enroll(body: EnrollIn, request: Request) -> dict:
    wait = ratelimit.check(f"enroll:{request.client.host if request.client else '?'}", 20)
    if wait is not None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "muitas tentativas", headers={"Retry-After": str(wait)})
    with anonymous_session() as s:
        row = s.execute(text("SELECT token_id, tenant_id FROM enroll_consume(:h)"), {"h": _hash(body.token)}).first()
    if row is None:  # token inexistente, expirado, revogado ou esgotado: a mesma resposta para não ajudar quem adivinha
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token de matrícula inválido")
    key, prefix, digest = generate_api_key()
    with tenant_session(row.tenant_id) as s:
        k = ApiKey(tenant_id=row.tenant_id, name=f"dispositivo:{body.hostname}"[:120], prefix=prefix, key_hash=digest, scopes=["ingest"])
        s.add(k)
        s.flush()
        d = Device(tenant_id=row.tenant_id, token_id=row.token_id, api_key_id=k.id, hostname=body.hostname, os=body.os,
                   client_version=body.client_version, tools=sorted(set(body.tools)))
        s.add(d)
        s.flush()
        audit_system.write(s, row.tenant_id, "device.enroll", "device", str(d.id), {"hostname": body.hostname, "tools": d.tools})
        return {"device_id": str(d.id), "api_key": key}


def _device_view(d: Device, k: ApiKey | None) -> dict:
    last = k.last_used_at if k else None
    return {"id": str(d.id), "hostname": d.hostname, "os": d.os, "client_version": d.client_version, "tools": d.tools,
            "enrolled_at": d.enrolled_at.isoformat(), "last_seen_at": last.isoformat() if last else None,
            "revoked": d.revoked_at is not None}


@router.get("/devices", summary="Máquinas matriculadas e cobertura por ferramenta")
def list_devices(p: Annotated[Principal, Depends(require_roles(*READ_ROLES))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        rows = s.execute(select(Device, ApiKey).outerjoin(ApiKey, ApiKey.id == Device.api_key_id).order_by(Device.enrolled_at.desc())).all()
        devices = [_device_view(d, k) for d, k in rows]
    active = [d for d in devices if not d["revoked"]]
    coverage: dict[str, int] = {}
    for d in active:
        for t in d["tools"]:
            coverage[t] = coverage.get(t, 0) + 1
    return {"devices": devices, "active": len(active), "coverage": coverage}


@router.post("/devices/{device_id}/revoke")
def revoke_device(device_id: uuid.UUID, p: Annotated[Principal, Depends(require_roles("admin"))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        d = s.get(Device, device_id)
        if d is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "dispositivo não encontrado")
        now = datetime.now(timezone.utc)
        d.revoked_at = d.revoked_at or now
        k = s.get(ApiKey, d.api_key_id) if d.api_key_id else None
        if k is not None:
            k.revoked_at = k.revoked_at or now
        audit.write(s, p, "device.revoke", "device", str(d.id), {"hostname": d.hostname})
        return _device_view(d, k)
