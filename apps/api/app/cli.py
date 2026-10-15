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
    d = sub.add_parser("seed-demo", help="gera eventos SINTÉTICOS e marca o tenant como demonstração")
    d.add_argument("--slug", required=True)
    d.add_argument("--days", type=int, default=14)
    d.add_argument("--count", type=int, default=400)
    u = sub.add_parser("create-user")
    u.add_argument("--slug", required=True)
    u.add_argument("--email", required=True)
    u.add_argument("--role", required=True, choices=["admin", "analista", "auditor", "leitura"])
    sub.add_parser("rewrap-keys", help="troca a chave mestra: reembrulha as chaves de dados (lê OLD_MASTER_KEY e NEW_MASTER_KEY do ambiente)")
    args = ap.parse_args()
    url = settings.admin_database_url or settings.database_url
    if args.cmd == "seed-demo":
        from app.demo import seed_demo

        with Session(create_engine(url)) as s, s.begin():
            print(seed_demo(s, args.slug, args.days, args.count))
        return
    if args.cmd == "rewrap-keys":
        import os

        from app import crypto

        old, new = os.environ.get("OLD_MASTER_KEY"), os.environ.get("NEW_MASTER_KEY")
        if not old or not new or old == new:
            raise SystemExit("defina OLD_MASTER_KEY e NEW_MASTER_KEY (diferentes), em base64 urlsafe de 32 bytes")
        with Session(create_engine(url)) as s, s.begin():
            print("chaves reembrulhadas:", crypto.rewrap_keys(s, old, new))
        return
    if args.cmd == "create-user":
        with Session(create_engine(url)) as s, s.begin():
            tid = s.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": args.slug}).scalar_one()
            s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tid)})
            s.add(User(tenant_id=tid, email=args.email, role=args.role))
        print("criado:", args.email, args.role)
        return
    with Session(create_engine(url)) as s, s.begin():
        out = create_tenant(s, args.name, args.slug, args.admin_email)
    print(f"tenant_id:  {out['tenant_id']}\nadmin:      {args.admin_email}\napi_key:    {out['api_key']}\n"
          "Guarde a chave agora: ela não pode ser recuperada.")


if __name__ == "__main__":
    main()
