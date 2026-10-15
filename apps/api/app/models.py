import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _tenant() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)


def _ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = _ts()
    store_original: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_mode: Mapped[str] = mapped_column(String(10), default="open")
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    policy_url: Mapped[str | None] = mapped_column(String(500))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    volume_threshold_per_hour: Mapped[int] = mapped_column(Integer, default=60)
    original_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    last_retention_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    monitored_domains: Mapped[list[str]] = mapped_column(ARRAY(String), default=lambda: ["chatgpt.com", "claude.ai"])


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    department: Mapped[str | None] = mapped_column(String(120))
    groups: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts()


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), default=lambda: ["ingest"])
    created_at: Mapped[datetime] = _ts()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    match: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    action: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(10), default="monitor")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


class Event(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = _ts()
    channel: Mapped[str] = mapped_column(String(30))
    app: Mapped[str] = mapped_column(String(80))
    integration_status: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(120))
    device_id: Mapped[str | None] = mapped_column(String(200))
    agent_id: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    session_id: Mapped[str | None] = mapped_column(String(200))
    personal_account: Mapped[bool] = mapped_column(Boolean, default=False)
    tool_name: Mapped[str | None] = mapped_column(String(120))
    masked_text: Mapped[str] = mapped_column(Text)
    text_length: Mapped[int] = mapped_column(Integer)
    original_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    event_pk: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("events.id", ondelete="CASCADE"), unique=True)
    categories: Mapped[list[Any]] = mapped_column(JSON)
    flags: Mapped[dict[str, Any]] = mapped_column(JSON)
    risk_score: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[list[Any]] = mapped_column(JSON)
    spans: Mapped[list[Any]] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(20))
    would_decide: Mapped[str] = mapped_column(String(20))
    policy_hits: Mapped[list[Any]] = mapped_column(JSON)
    score_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = _ts()


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    event_pk: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("events.id", ondelete="CASCADE"), unique=True)
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="aberto")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = _tenant()
    at: Mapped[datetime] = _ts()
    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(200))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    target: Mapped[str] = mapped_column(String(1000))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    target_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts()


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    rule: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))
    dedup_key: Mapped[str] = mapped_column(String(300))
    user_id: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(120))
    event_pk: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("events.id", ondelete="SET NULL"))
    incident_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("incidents.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen: Mapped[datetime] = _ts()
    last_seen: Mapped[datetime] = _ts()


class OutboxItem(Base):
    __tablename__ = "notification_outbox"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    channel_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("notification_channels.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))
    ref_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = _ts()
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = _ts()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    kind: Mapped[str] = mapped_column(String(20))
    format: Mapped[str] = mapped_column(String(5))
    frequency: Mapped[str] = mapped_column(String(10))
    recipients: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_period_end: Mapped[Any | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts()


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    kind: Mapped[str] = mapped_column(String(20))
    format: Mapped[str] = mapped_column(String(5))
    period_start: Mapped[Any] = mapped_column(Date)
    period_end: Mapped[Any] = mapped_column(Date)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(200))
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("report_schedules.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _ts()


class InferenceHookConfig(Base):
    __tablename__ = "inference_hook_configs"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    mode: Mapped[str] = mapped_column(String(10), default="shadow")
    scope: Mapped[str] = mapped_column(String(10), default="full")
    evaluate_tool_calls: Mapped[bool] = mapped_column(Boolean, default=True)
    secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    previous_secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    previous_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    last_rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


class InferenceHookRequest(Base):
    __tablename__ = "inference_hook_requests"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    request_id: Mapped[str] = mapped_column(String(200))
    frame_type: Mapped[str] = mapped_column(String(40))
    application: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(20))
    would_deny: Mapped[bool] = mapped_column(Boolean, default=False)
    blocks_total: Mapped[int] = mapped_column(Integer, default=0)
    blocks_new: Mapped[int] = mapped_column(Integer, default=0)
    skipped_attachments: Mapped[int] = mapped_column(Integer, default=0)
    categories: Mapped[list[Any]] = mapped_column(JSON, default=list)
    reference_id: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = _ts()
