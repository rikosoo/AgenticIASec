"""Licença por empresa: limite de máquinas ATIVAS (vistas, ou matriculadas, nos últimos 45 dias) e validade.

O limite só barra NOVAS matrículas: máquinas já instaladas continuam enviando eventos (a empresa não fica às cegas por causa de contrato).
Quem define o limite é o fornecedor (python -m app.cli set-license); a API do administrador da empresa não tem como alterá-lo."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

ACTIVE_WINDOW_DAYS = 45

_SEATS = text("""
    SELECT count(*) FROM devices d LEFT JOIN api_keys k ON k.id = d.api_key_id
    WHERE d.tenant_id = :t AND d.revoked_at IS NULL
      AND greatest(coalesce(k.last_used_at, d.enrolled_at), d.enrolled_at) >= :cutoff""")


def cutoff(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)) - timedelta(days=ACTIVE_WINDOW_DAYS)


def active_seats(session: Session, tenant_id: uuid.UUID, now: datetime | None = None) -> int:
    return int(session.execute(_SEATS, {"t": tenant_id, "cutoff": cutoff(now)}).scalar_one())


def summary(session: Session, tenant, now: datetime | None = None) -> dict:
    used = active_seats(session, tenant.id, now)
    mx = tenant.max_devices
    level = "ok"
    if mx is not None:
        level = "esgotada" if used >= mx else "alerta" if mx and used >= 0.8 * mx else "ok"
    expired = bool(tenant.license_expires_at and tenant.license_expires_at <= (now or datetime.now(timezone.utc)))
    return {"max_devices": mx, "active_seats": used, "window_days": ACTIVE_WINDOW_DAYS, "level": level, "expired": expired,
            "expires_at": tenant.license_expires_at.isoformat() if tenant.license_expires_at else None}


class Refused(Exception):
    """Matrícula recusada pela licença (a transação inteira, inclusive o uso do token, é desfeita)."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason, self.detail = reason, detail


def check_new_seat(session: Session, tenant, now: datetime | None = None) -> None:
    """Chamar com o tenant TRAVADO (FOR UPDATE) e depois de liberar a vaga de uma reinstalação."""
    now = now or datetime.now(timezone.utc)
    if getattr(tenant, "suspended_at", None):
        raise Refused("suspended", "o contrato desta empresa está suspenso: novas máquinas não podem ser matriculadas. Fale com o fornecedor.")
    if tenant.license_expires_at and tenant.license_expires_at <= now:
        raise Refused("license_expired", "a licença desta empresa expirou: novas máquinas não podem ser matriculadas. Fale com o fornecedor.")
    if tenant.max_devices is not None:
        used = active_seats(session, tenant.id, now)
        if used >= tenant.max_devices:
            raise Refused("limit_reached", f"limite de máquinas da licença atingido ({used} de {tenant.max_devices} ativas nos últimos "
                                           f"{ACTIVE_WINDOW_DAYS} dias). Revogue máquinas que não são mais usadas ou fale com o fornecedor.")
