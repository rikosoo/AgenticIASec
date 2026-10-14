from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app import audit
from app.db import tenant_session
from app.models import ApiKey, AuditLog, Tenant, User
from app.schemas import ApiKeyIn, TenantPatch, UserIn
from app.security import Principal, current_principal, generate_api_key, require_ingest, require_roles

router = APIRouter(prefix="/v1", tags=["administração"])


@router.get("/me")
def me(p: Annotated[Principal, Depends(current_principal)]) -> dict:
    return {"kind": p.kind, "id": p.id, "tenant_id": str(p.tenant_id), "role": p.role, "email": p.email}


@router.get("/users/directory", summary="Pessoas que podem receber incidentes")
def user_directory(p: Annotated[Principal, Depends(require_roles("admin", "analista"))]) -> list[dict]:
    with tenant_session(p.tenant_id) as s:
        rows = s.execute(select(User).where(User.active.is_(True)).order_by(User.email)).scalars()
        return [{"id": str(u.id), "email": u.email, "display_name": u.display_name, "role": u.role} for u in rows]


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



def _tenant_view(t: Tenant) -> dict:
    return {"id": str(t.id), "name": t.name, "failure_mode": t.failure_mode, "retention_days": t.retention_days,
            "store_original": t.store_original, "policy_url": t.policy_url, "monitored_domains": t.monitored_domains,
            "is_demo": t.is_demo}


@router.get("/tenant", summary="Configurações do tenant")
def get_tenant(p: Annotated[Principal, Depends(require_roles("admin", "analista", "auditor", "leitura"))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        return _tenant_view(s.get(Tenant, p.tenant_id))


@router.patch("/tenant", summary="Altera modo de falha, retenção ou guarda do texto original (grava auditoria)")
def patch_tenant(body: TenantPatch, p: Annotated[Principal, Depends(require_roles("admin"))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        t = s.get(Tenant, p.tenant_id)
        before = _tenant_view(t)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(t, k, v)
        s.flush()
        audit.write(s, p, "tenant.update", "tenant", str(p.tenant_id), {"before": before, "after": _tenant_view(t)})
        return _tenant_view(t)


@router.get("/hook-config", summary="Configuração mínima para coletores (modo de falha)")
def hook_config(p: Annotated[Principal, Depends(require_ingest)]) -> dict:
    with tenant_session(p.tenant_id) as s:
        t = s.get(Tenant, p.tenant_id)
        return {"failure_mode": t.failure_mode}


@router.get("/extension-config", summary="Configuração para a extensão de navegador (domínios, política, modo de falha)")
def extension_config(p: Annotated[Principal, Depends(require_ingest)]) -> dict:
    with tenant_session(p.tenant_id) as s:
        t = s.get(Tenant, p.tenant_id)
        return {"failure_mode": t.failure_mode, "domains": list(t.monitored_domains), "policy_url": t.policy_url}
