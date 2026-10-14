"""Operação: cria tenant com admin, chave de API e políticas padrão (todas em modo monitor).

    python -m app.cli create-tenant --name "Empresa" --slug empresa --admin-email admin@empresa.com.br

Usa ADMIN_DATABASE_URL (dono do banco). A chave de API é impressa uma única vez.
"""
from __future__ import annotations

import argparse
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ApiKey, Tenant, User
from app.security import generate_api_key
from app.services import seed_default_policies


def create_tenant(session: Session, name: str, slug: str, admin_email: str, key_name: str = "coletor-padrao") -> dict[str, str]:
    tenant_id = uuid.uuid4()
    session.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
    session.add(Tenant(id=tenant_id, name=name, slug=slug))
    session.flush()
    admin = User(tenant_id=tenant_id, email=admin_email, role="admin", display_name="Administrador")
    session.add(admin)
    key, prefix, digest = generate_api_key()
    session.add(ApiKey(tenant_id=tenant_id, name=key_name, prefix=prefix, key_hash=digest, scopes=["ingest"]))
    seed_default_policies(session, tenant_id)
    session.flush()
    return {"tenant_id": str(tenant_id), "admin_user_id": str(admin.id), "api_key": key}


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-tenant")
    c.add_argument("--name", required=True)
    c.add_argument("--slug", required=True)
    c.add_argument("--admin-email", required=True)
    args = ap.parse_args()
    url = settings.admin_database_url or settings.database_url
    with Session(create_engine(url)) as s, s.begin():
        out = create_tenant(s, args.name, args.slug, args.admin_email)
    print(f"tenant_id:  {out['tenant_id']}\nadmin:      {args.admin_email}\napi_key:    {out['api_key']}\n"
          "Guarde a chave agora: ela não pode ser recuperada.")


if __name__ == "__main__":
    main()
