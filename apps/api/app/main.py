from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="PromptShield API", version=settings.version)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": settings.version}
