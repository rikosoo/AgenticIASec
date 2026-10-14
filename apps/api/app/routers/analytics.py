"""Números do painel: tudo calculado no banco, por tenant (RLS). Nada fixo no código."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from promptshield_detection.taxonomy import load as load_taxonomy
from sqlalchemy import text

from app.db import tenant_session
from app.security import READ_ROLES, Principal, require_roles

router = APIRouter(prefix="/v1", tags=["painel"])
HIGH = 60


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


@router.get("/taxonomy", summary="As 30 categorias (id, nome, grupo, risco padrão)")
def taxonomy(_: Annotated[Principal, Depends(require_roles(*READ_ROLES))]) -> list[dict]:
    return [{"id": c.id, "nome": c.nome, "grupo": c.grupo, "risco_padrao": c.risco_padrao} for c in load_taxonomy().values()]


@router.get("/stats/overview", summary="Indicadores, série diária de alto risco, departamentos e ferramentas")
def overview(p: Annotated[Principal, Depends(require_roles(*READ_ROLES))], days: int = Query(14, ge=1, le=90)) -> dict:
    since = _since(days)
    with tenant_session(p.tenant_id) as s:
        row = s.execute(text("""
            SELECT count(*) AS events,
                   count(*) FILTER (WHERE a.risk_score >= :hi) AS high_risk,
                   count(*) FILTER (WHERE (a.flags::jsonb)->>'has_code' = 'true') AS with_code,
                   count(*) FILTER (WHERE (a.flags::jsonb)->>'has_sensitive' = 'true') AS with_sensitive,
                   count(*) FILTER (WHERE (a.flags::jsonb)->>'is_agent_action' = 'true') AS agent_actions,
                   count(*) FILTER (WHERE a.decision = 'block') AS blocked,
                   count(*) FILTER (WHERE a.would_decide = 'block' AND a.decision <> 'block') AS would_block,
                   count(DISTINCT e.user_id) AS users
            FROM events e JOIN analyses a ON a.event_pk = e.id WHERE e.occurred_at >= :since"""), {"hi": HIGH, "since": since}).mappings().one()
        daily = {r.d: (r.total, r.high) for r in s.execute(text("""
            SELECT (e.occurred_at AT TIME ZONE 'UTC')::date AS d, count(*) AS total,
                   count(*) FILTER (WHERE a.risk_score >= :hi) AS high
            FROM events e JOIN analyses a ON a.event_pk = e.id WHERE e.occurred_at >= :since GROUP BY 1"""), {"hi": HIGH, "since": since})}
        by_dept = s.execute(text("""
            SELECT coalesce(e.department, '(sem departamento)') AS department, count(*) AS events,
                   count(*) FILTER (WHERE a.risk_score >= :hi) AS high_risk
            FROM events e JOIN analyses a ON a.event_pk = e.id WHERE e.occurred_at >= :since
            GROUP BY 1 ORDER BY 3 DESC, 2 DESC"""), {"hi": HIGH, "since": since}).mappings().all()
        by_app = s.execute(text("""
            SELECT e.app, count(*) FILTER (WHERE NOT e.personal_account) AS corporate,
                   count(*) FILTER (WHERE e.personal_account) AS personal
            FROM events e WHERE e.occurred_at >= :since GROUP BY 1 ORDER BY count(*) DESC"""), {"since": since}).mappings().all()
    today = datetime.now(timezone.utc).date()
    series = []
    for i in range(days - 1, -1, -1):
        d: date = today - timedelta(days=i)
        total, high = daily.get(d, (0, 0))
        series.append({"date": d.isoformat(), "events": total, "high_risk": high})
    return {"days": days, "high_risk_threshold": HIGH, "totals": dict(row), "daily": series,
            "by_department": [dict(r) for r in by_dept], "by_app": [dict(r) for r in by_app]}


@router.get("/stats/categories", summary="Quantos eventos por categoria (confiança de 0,5 ou mais)")
def category_counts(p: Annotated[Principal, Depends(require_roles(*READ_ROLES))], days: int = Query(14, ge=1, le=90)) -> dict[str, int]:
    with tenant_session(p.tenant_id) as s:
        rows = s.execute(text("""
            SELECT c->>'id' AS id, count(*) AS n
            FROM events e JOIN analyses a ON a.event_pk = e.id, jsonb_array_elements(a.categories::jsonb) c
            WHERE e.occurred_at >= :since GROUP BY 1"""), {"since": _since(days)})
        return {r.id: r.n for r in rows}
