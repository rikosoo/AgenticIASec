from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app import audit
from app.db import tenant_session
from app.models import ApiKey, AuditLog, User
from app.schemas import ApiKeyIn, UserIn
from app.security import READ_ROLES, Principal, current_principal, generate_api_key, require_roles

router = APIRouter(prefix="/v1", tags=["administração"])


@router.get("/me")
def me(p: Annotated[Principal, Depends(current_principal)]) -> dict:
    return {"kind": p.kind, "id": p.id, "tenant_id": str(p.tenant_id), "role": p.role, "email": p.email}


@router.get("/users")
def list_users(p: Annotated[Principal, Depends(require_roles("admin"))]) -> list[dict]:
    with tenant_session(p.tenant_id) as s:
        return [{"id": str(u.id), "email": u.email, "role": u.role, "department": u.department, "groups": u.groups, "active": u.active}
                for u in s.execute(select(User).order_by(User.email)).scalars()]


@router.post("/users", status_code=201)
def create_user(body: UserIn, p: Annotated[Principal, Depends(require_roles("admin"))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        u = User(tenant_id=p.tenant_id, **body.model_dump())
        s.add(u)
        try:
            s.flush()
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "e-mail já cadastrado") from exc
        audit.write(s, p, "user.create", "user", str(u.id), {"email": u.email, "role": u.role})
        return {"id": str(u.id), "email": u.email, "role": u.role}


@router.post("/api-keys", status_code=201, summary="Cria chave de API; o valor completo aparece só nesta resposta")
def create_key(body: ApiKeyIn, p: Annotated[Principal, Depends(require_roles("admin"))]) -> dict:
    key, prefix, digest = generate_api_key()
    with tenant_session(p.tenant_id) as s:
        k = ApiKey(tenant_id=p.tenant_id, name=body.name, prefix=prefix, key_hash=digest, scopes=["ingest"])
        s.add(k)
        s.flush()
        audit.write(s, p, "api_key.create", "api_key", str(k.id), {"name": body.name, "prefix": prefix})
        return {"id": str(k.id), "name": k.name, "prefix": prefix, "key": key}


@router.get("/api-keys")
def list_keys(p: Annotated[Principal, Depends(require_roles("admin"))]) -> list[dict]:
    with tenant_session(p.tenant_id) as s:
        return [{"id": str(k.id), "name": k.name, "prefix": k.prefix, "revoked": k.revoked_at is not None,
                 "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None}
                for k in s.execute(select(ApiKey).order_by(ApiKey.created_at)).scalars()]


@router.post("/api-keys/{key_id}/revoke")
def revoke_key(key_id: uuid.UUID, p: Annotated[Principal, Depends(require_roles("admin"))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        k = s.get(ApiKey, key_id)
        if k is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "chave não encontrada")
        s.execute(text("UPDATE api_keys SET revoked_at = now() WHERE id = :i AND revoked_at IS NULL"), {"i": key_id})
        audit.write(s, p, "api_key.revoke", "api_key", str(key_id), {"prefix": k.prefix})
        return {"id": str(key_id), "revoked": True}


@router.get("/audit-log")
def audit_log(p: Annotated[Principal, Depends(require_roles("admin", "auditor"))], limit: int = 100) -> list[dict]:
    with tenant_session(p.tenant_id) as s:
        rows = s.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500))).scalars()
        return [{"id": r.id, "at": r.at.isoformat(), "actor": r.actor_id, "action": r.action, "target_type": r.target_type,
                 "target_id": r.target_id, "detail": r.detail} for r in rows]


_ = READ_ROLES
