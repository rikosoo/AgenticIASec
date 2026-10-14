from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text

from app import audit
from app.db import tenant_session
from app.models import Policy
from app.schemas import PolicyIn, PolicyOut
from app.security import READ_ROLES, Principal, require_roles

router = APIRouter(prefix="/v1/policies", tags=["políticas"])


def _out(p: Policy) -> PolicyOut:
    return PolicyOut(id=p.id, name=p.name, description=p.description, enabled=p.enabled, scope=p.scope or {}, match=p.match or {},
                     action=p.action, mode=p.mode, version=p.version, updated_at=p.updated_at)  # type: ignore[arg-type]


def _snapshot(p: Policy) -> dict:
    return {"name": p.name, "enabled": p.enabled, "scope": p.scope, "match": p.match, "action": p.action, "mode": p.mode, "version": p.version}


@router.get("", response_model=list[PolicyOut])
def list_policies(p: Annotated[Principal, Depends(require_roles(*READ_ROLES))]) -> list[PolicyOut]:
    with tenant_session(p.tenant_id) as s:
        return [_out(x) for x in s.execute(select(Policy).order_by(Policy.name)).scalars()]


@router.post("", response_model=PolicyOut, status_code=201, summary="Cria política (nasce em modo monitor por padrão)")
def create_policy(body: PolicyIn, p: Annotated[Principal, Depends(require_roles("admin"))]) -> PolicyOut:
    with tenant_session(p.tenant_id) as s:
        pol = Policy(tenant_id=p.tenant_id, **body.model_dump())
        s.add(pol)
        s.flush()
        audit.write(s, p, "policy.create", "policy", str(pol.id), {"after": _snapshot(pol)})
        s.refresh(pol)
        return _out(pol)


@router.put("/{policy_id}", response_model=PolicyOut, summary="Altera política (grava auditoria com antes e depois)")
def update_policy(policy_id: uuid.UUID, body: PolicyIn, p: Annotated[Principal, Depends(require_roles("admin"))]) -> PolicyOut:
    with tenant_session(p.tenant_id) as s:
        pol = s.get(Policy, policy_id)
        if pol is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "política não encontrada")
        before = _snapshot(pol)
        for k, v in body.model_dump().items():
            setattr(pol, k, v)
        pol.version += 1
        s.execute(text("UPDATE policies SET updated_at = now() WHERE id = :i"), {"i": policy_id})
        s.flush()
        audit.write(s, p, "policy.update", "policy", str(policy_id), {"before": before, "after": _snapshot(pol)})
        s.refresh(pol)
        return _out(pol)
