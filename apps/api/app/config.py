from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # papel da aplicação (sem BYPASSRLS); usado pela API em runtime
    database_url: str = "postgresql+psycopg://promptshield_app:promptshield_app@localhost:5432/promptshield"
    # dono/superuser: só para migrações e CLI (Alembic e `python -m app.cli`)
    admin_database_url: str | None = None
    version: str = "0.3.0"

    # origens com permissão de CORS, separadas por vírgula (ex.: chrome-extension://<id>,https://console.empresa.com). Padrão: nenhuma.
    cors_allowed_origins: str = ""

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

    # notificações (Etapa 7). Webhooks exigem https e destino público, salvo estas válvulas de desenvolvimento/teste.
    allow_insecure_webhooks: bool = False
    allow_private_webhook_targets: bool = False
    webhook_timeout_seconds: float = 5.0
    outbox_max_attempts: int = 5
    # e-mail: sem smtp_host o envio por e-mail falha com mensagem clara (nada é fingido)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "promptshield@localhost"
    smtp_starttls: bool = True
    # endereço do console, usado nos links das notificações (opcional)
    console_url: str | None = None

    # inference hooks do Claude Enterprise (Etapa 8). O orçamento fica abaixo do tempo limite padrão da Anthropic (5.000 ms).
    inference_hook_budget_ms: int = 3000
    inference_hook_max_body_bytes: int = 64 * 1024 * 1024  # o protocolo permite até 64 MiB
    inference_hook_previous_secret_minutes: int = 10  # a troca de segredo é imediata do lado da Anthropic; aceitamos o anterior por um tempo


settings = Settings()
