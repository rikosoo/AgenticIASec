from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://promptshield:promptshield@localhost:5432/promptshield"
    version: str = "0.1.0"


settings = Settings()
