# Contexto de build: raiz do repositório (ver docker-compose.yml)
FROM python:3.12-slim
WORKDIR /srv
COPY packages ./packages
COPY apps/api ./apps/api
RUN pip install --no-cache-dir -e packages/detection -e apps/api
WORKDIR /srv/apps/api
EXPOSE 8000
# migra com o dono do banco (ADMIN_DATABASE_URL) e serve com o papel restrito (DATABASE_URL)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
