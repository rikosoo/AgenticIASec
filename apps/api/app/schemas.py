from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Channel = Literal["browser", "agent_hook", "api_proxy", "inference_hook"]
Integration = Literal["real", "partial", "experimental"]
Kind = Literal["prompt", "response", "tool_call", "tool_result", "file_upload"]
Action = Literal["allow", "mask", "block", "ask_justification", "alert"]


class Source(BaseModel):
    channel: Channel
    app: str = Field(min_length=1, max_length=80)
    integration_status: Integration


class Actor(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    department: str | None = Field(default=None, max_length=120)
    device_id: str | None = Field(default=None, max_length=200)
    agent_id: str | None = Field(default=None, max_length=200)
    groups: list[str] = Field(default_factory=list, max_length=50)  # extensão ao evento universal: escopo de política por grupo


class Content(BaseModel):
    text: str | None = None
    tool_name: str | None = Field(default=None, max_length=120)
    tool_input: dict[str, Any] | None = None


class Context(BaseModel):
    session_id: str | None = Field(default=None, max_length=200)
    personal_account: bool = False


class EventIn(BaseModel):
    """Evento universal (CLAUDE.md). `tenant_id`, se enviado, precisa coincidir com o da chave."""

    model_config = ConfigDict(extra="forbid")
    event_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    occurred_at: datetime
    source: Source
    actor: Actor
    kind: Kind
    content: Content
    context: Context = Field(default_factory=Context)


class SpanOut(BaseModel):
    start: int
    end: int
    type: str
    masked: str


class EventResult(BaseModel):
    event_id: uuid.UUID
    decision: Action
    would_decide: Action
    enforced: bool
    masked_text: str
    categories: list[dict[str, Any]]
    flags: dict[str, bool]
    risk: dict[str, Any]
    spans: list[SpanOut]
    policy_hits: list[dict[str, str]]
    incident_id: uuid.UUID | None = None
    duplicate: bool = False


class PolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    enabled: bool = True
    scope: dict[str, list[str]] = Field(default_factory=dict)
    match: dict[str, Any] = Field(default_factory=dict)
    action: Action
    mode: Literal["monitor", "enforce"] = "monitor"  # padrão seguro


class PolicyOut(PolicyIn):
    id: uuid.UUID
    version: int
    updated_at: datetime


class IncidentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["aberto", "em analise", "resolvido", "falso positivo"] | None = None
    assignee_id: uuid.UUID | None = None


class OriginalRequest(BaseModel):
    justification: str = Field(min_length=10, max_length=1000)


class UserIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    display_name: str | None = None
    role: Literal["admin", "analista", "auditor", "leitura"]
    department: str | None = None
    groups: list[str] = Field(default_factory=list)


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
