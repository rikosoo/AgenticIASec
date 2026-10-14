from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.expression import cast

from app import audit, crypto
from app.db import tenant_session
from app.models import Analysis, Event
from app.schemas import EventIn, EventResult, JustificationIn, OriginalRequest
from app.security import READ_ROLES, Principal, require_ingest, require_roles
from app.services import ingest

router = APIRouter(prefix="/v1/events", tags=["eventos"])


@router.post("", response_model=EventResult, summary="Recebe um evento universal, analisa e devolve a decisão")
def post_event(ev: EventIn, p: Annotated[Principal, Depends(require_ingest)]) -> EventResult:
    with tenant_session(p.tenant_id) as s:
        return ingest(s, p, ev)


@router.get("", summary="Lista eventos (texto sempre mascarado); filtros para a análise de prompts. Total no header X-Total-Count")
def list_events(
    response: Response,
    p: Annotated[Principal, Depends(require_roles(*READ_ROLES))],
    user_id: str | None = None, min_score: int = Query(0, ge=0, le=100),
    category: str | None = Query(None, description="id da categoria da taxonomia"),
    has_code: bool | None = None, has_sensitive: bool | None = None, agent_action: bool | None = None,
    only_blocked: bool = Query(False, description="decisão block, ou que seria block em modo monitorar"),
    department: str | None = None, app: str | None = None, personal_account: bool | None = None,
    days: int | None = Query(None, ge=1, le=365), sort: str = Query("recent", pattern="^(recent|risk)$"),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
) -> list[dict]:
    with tenant_session(p.tenant_id) as s:
        q = select(Event, Analysis).join(Analysis, Analysis.event_pk == Event.id).where(Analysis.risk_score >= min_score)
        if user_id:
            q = q.where(Event.user_id == user_id)
        if department:
            q = q.where(Event.department == department)
        if app:
            q = q.where(Event.app == app)
        if personal_account is not None:
            q = q.where(Event.personal_account.is_(personal_account))
        if days:
            q = q.where(Event.occurred_at >= datetime.now(timezone.utc) - timedelta(days=days))
        if category:
            q = q.where(cast(Analysis.categories, JSONB).contains([{"id": category}]))
        for key, flag in (("has_code", has_code), ("has_sensitive", has_sensitive), ("is_agent_action", agent_action)):
            if flag is not None:
                q = q.where(cast(Analysis.flags, JSONB).contains({key: flag}))
        if only_blocked:
            q = q.where((Analysis.decision == "block") | (Analysis.would_decide == "block"))
        total = s.execute(select(func.count()).select_from(q.subquery())).scalar_one()
        order = (Analysis.risk_score.desc(), Event.occurred_at.desc()) if sort == "risk" else (Event.occurred_at.desc(),)
        rows = s.execute(q.order_by(*order).limit(limit).offset(offset)).all()
        response.headers["X-Total-Count"] = str(total)
        return [_view(e, a) for e, a in rows]


@router.get("/{event_id}", summary="Detalhe de um evento (texto mascarado)")
def get_event(event_id: uuid.UUID, p: Annotated[Principal, Depends(require_roles(*READ_ROLES))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        row = s.execute(select(Event, Analysis).join(Analysis, Analysis.event_pk == Event.id)
                        .where(Event.event_id == event_id)).first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "evento não encontrado")
        return _view(*row)


@router.post("/{event_id}/justification", status_code=204,
             summary="Registra a justificativa do usuário para enviar mesmo assim (política ask_justification)")
def post_justification(event_id: uuid.UUID, body: JustificationIn, p: Annotated[Principal, Depends(require_ingest)]) -> None:
    with tenant_session(p.tenant_id) as s:
        if s.execute(select(Event.id).where(Event.event_id == event_id)).scalar() is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "evento não encontrado")
        audit.write(s, p, "event.justification", "event", str(event_id), {"justification": body.justification})


@router.post("/{event_id}/original", summary="Lê o texto original (exige justificativa; grava auditoria)")
def read_original(event_id: uuid.UUID, body: OriginalRequest,
                  p: Annotated[Principal, Depends(require_roles("admin", "analista"))]) -> dict:
    with tenant_session(p.tenant_id) as s:
        ev = s.execute(select(Event).where(Event.event_id == event_id)).scalar()
        if ev is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "evento não encontrado")
        # o pedido fica registrado mesmo quando não há original guardado
        audit.write(s, p, "event.original_read", "event", str(event_id),
                    {"justification": body.justification, "available": ev.original_ciphertext is not None})
        if ev.original_ciphertext is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "este tenant não guarda o texto original deste evento")
        return {"event_id": str(event_id), "text": crypto.decrypt_original(p.tenant_id, ev.original_ciphertext)}


def _view(e: Event, a: Analysis) -> dict:
    return {"event_id": str(e.event_id), "occurred_at": e.occurred_at.isoformat(), "app": e.app, "channel": e.channel,
            "user_id": e.user_id, "department": e.department, "kind": e.kind, "personal_account": e.personal_account,
            "masked_text": e.masked_text, "has_original": e.original_ciphertext is not None,
            "categories": a.categories, "flags": a.flags, "risk_score": a.risk_score, "reasons": a.reasons,
            "decision": a.decision, "would_decide": a.would_decide, "policy_hits": a.policy_hits}
