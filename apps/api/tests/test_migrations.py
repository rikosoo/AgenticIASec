"""Roda a migração em um banco de verdade. Pula se DATABASE_URL_TEST não estiver definida."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

URL = os.environ.get("DATABASE_URL_TEST")
API_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not URL, reason="DATABASE_URL_TEST não definida")
def test_upgrade_and_downgrade_tenants():
    env = {**os.environ, "DATABASE_URL": URL}
    def run(*args: str) -> None:
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=API_DIR, env=env, check=True)

    run("upgrade", "head")
    cols = {c["name"] for c in inspect(create_engine(URL)).get_columns("tenants")}
    assert {"id", "name", "slug", "created_at"} <= cols
    run("downgrade", "base")
    assert "tenants" not in inspect(create_engine(URL)).get_table_names()
