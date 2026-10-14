from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # papel da aplicação (sem BYPASSRLS); usado pela API em runtime
    database_url: str = "postgresql+psycopg://promptshield_app:promptshield_app@localhost:5432/promptshield"
    # dono/superuser: só para migrações e CLI (Alembic e `python -m app.cli`)
    admin_database_url: str | None = None
    version: str = "0.3.0"

    max_text_chars: int = 2_000_000
    enable_ner: bool = False

    # texto original (opcional por tenant). Chave mestra em base64 de 32 bytes. Interino até o KMS por tenant (Etapa 9).
    original_text_master_key: str | None = None

    # login do console: off | mock (só desenvolvimento) | oidc
    oidc_mode: str = "off"
    oidc_mock_secret: str | None = None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None


settings = Settings()
