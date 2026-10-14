from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app import services
from app.config import settings
from app.routers import admin, events, incidents, policies


@asynccontextmanager
async def lifespan(_: FastAPI):
    services.init_ner()
    yield


app = FastAPI(title="PromptShield API", version=settings.version, lifespan=lifespan,
              description="Ingestão de eventos, políticas e incidentes. Autenticação: `X-API-Key` (coletores) ou "
                          "`Authorization: Bearer <token OIDC>` (console).")


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version", tags=["infra"])
def version() -> dict[str, str]:
    return {"version": settings.version}


app.include_router(events.router)
app.include_router(incidents.router)
app.include_router(policies.router)
app.include_router(admin.router)

if settings.oidc_mode == "mock":  # só desenvolvimento: nunca registrado em outro modo
    from app.security import issue_mock_token

    class _Email(BaseModel):
        email: str

    @app.post("/dev/token", tags=["desenvolvimento"], summary="Token de login simulado (OIDC_MODE=mock)")
    def dev_token(body: _Email) -> dict[str, str]:
        return {"access_token": issue_mock_token(body.email), "token_type": "bearer"}
