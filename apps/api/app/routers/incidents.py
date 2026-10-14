from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text

from app import audit
from app.db import tenant_session
from app.models import Analysis, Event, Incident, User
from app.schemas import IncidentPatch
from app.security import READ_ROLES, Principal, require_roles

router = APIRouter(prefix="/v1/incidents", tags=["incidentes"])


def _view(i: Incident, e: Event, a: Analysis) -> dict:
    return {"id": str(i.id), "severity": i.severity, "status": i.status, "assignee_id": str(i.assignee_id) if i.assignee_id else None,
            "created_at": i.created_at.isoformat(), "event_id": str(e.event_id), "user_id": e.user_id, "app": e.app,
            "masked_text": e.masked_text, "categories": a.categories, "risk_score": a.risk_score, "reasons": a.reasons,
            "decision": a.decision, "would_decide": a.would_decide}


@router.get("", summary="Fila de incidentes")
def list_incidents(p: Annotated[Principal, Depends(require_roles(*READ_ROLES))], status_: str | None = Query(None, alias="status"),
                   severity: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> list[dict]:
    with tenant_session(p.tenant_id) as s:
        q = select(Incident, Event, Analysis).join(Event, Event.id == Incident.event_pk).join(Analysis, Analysis.event_pk == Event.id)
        if status_:
            q = q.where(Incident.status == status_)
        if severity:
            q = q.where(Incident.severity == severity)
        return [_view(*r) for r in s.execute(q.order_by(Incident.created_at.desc()).limit(limit).offset(offset)).all()]


@router.get("/{incident_id}")
def get_incident(incident_id: uuid.UUID, p: Annotated[Principal, Depends(require_roles(*READ_ROLES))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        r = s.execute(select(Incident, Event, Analysis).join(Event, Event.id == Incident.event_pk)
                      .join(Analysis, Analysis.event_pk == Event.id).where(Incident.id == incident_id)).first()
        if r is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "incidente não encontrado")
        return _view(*r)


@router.patch("/{incident_id}", summary="Altera status ou responsável")
def patch_incident(incident_id: uuid.UUID, body: IncidentPatch,
                   p: Annotated[Principal, Depends(require_roles("admin", "analista"))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        inc = s.get(Incident, incident_id)
        if inc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "incidente não encontrado")
        before = {"status": inc.status, "assignee_id": str(inc.assignee_id) if inc.assignee_id else None}
        if body.status:
            inc.status = body.status
        if "assignee_id" in body.model_fields_set:
            if body.assignee_id is not None and s.get(User, body.assignee_id) is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "responsável não existe neste tenant")
            inc.assignee_id = body.assignee_id
        s.execute(text("UPDATE incidents SET updated_at = now() WHERE id = :i"), {"i": incident_id})
        audit.write(s, p, "incident.update", "incident", str(incident_id),
                    {"before": before, "after": body.model_dump(mode="json", exclude_unset=True)})
        s.flush()
        r = s.execute(select(Incident, Event, Analysis).join(Event, Event.id == Incident.event_pk)
                      .join(Analysis, Analysis.event_pk == Event.id).where(Incident.id == incident_id)).first()
        return _view(*r)
