"""Matrícula de dispositivos: token revogável -> chave própria por máquina. Dados sintéticos; sem máquina real."""
import pytest
from conftest import event

pytestmark = pytest.mark.db


def make_token(client, world, **body):
    r = client.post("/v1/enrollment-tokens", json={"name": "piloto", **body}, headers=world.user("admin"))
    assert r.status_code == 201, r.text
    return r.json()


def enroll(client, token, host="NOTE-01", tools=("claude_code",)):
    return client.post("/v1/enroll", json={"token": token, "hostname": host, "os": "windows", "client_version": "0.1", "tools": list(tools)})


def test_token_becomes_a_device_key_that_ingests_and_can_be_revoked(client, world):
    t = make_token(client, world)
    assert t["token"].startswith("pse_") and "token_hash" not in t
    r = enroll(client, t["token"])
    assert r.status_code == 201
    key = r.json()["api_key"]
    assert key.startswith("ps_") and key != world.a["api_key"]
    assert client.post("/v1/events", json=event("SIMULADO oi"), headers={"X-API-Key": key}).status_code == 200
    d = client.get("/v1/devices", headers=world.user("leitura")).json()
    assert d["active"] == 1 and d["coverage"] == {"claude_code": 1} and d["devices"][0]["hostname"] == "NOTE-01"
    assert d["devices"][0]["last_seen_at"] is not None
    assert client.post(f"/v1/devices/{d['devices'][0]['id']}/revoke", headers=world.user("admin")).status_code == 200
    assert client.post("/v1/events", json=event("SIMULADO depois"), headers={"X-API-Key": key}).status_code == 401   # só esta máquina caiu
    assert client.post("/v1/events", json=event("SIMULADO ok"), headers=world.key()).status_code == 200
    assert client.get("/v1/devices", headers=world.user("leitura")).json()["active"] == 0


def test_revoked_expired_exhausted_and_unknown_tokens_are_refused_equally(client, world):
    rev = make_token(client, world)
    assert client.post(f"/v1/enrollment-tokens/{rev['id']}/revoke", headers=world.user("admin")).status_code == 200
    exp = make_token(client, world)
    world.sql("UPDATE enrollment_tokens SET expires_at = now() - interval '1 minute' WHERE id = :i", i=exp["id"])
    one = make_token(client, world, max_uses=1)
    assert enroll(client, one["token"]).status_code == 201
    msgs = set()
    for tok in (rev["token"], exp["token"], one["token"], "pse_00000000_inexistente-inexistente"):
        r = enroll(client, tok, host="X")
        assert r.status_code == 401
        msgs.add(r.json()["detail"])
    assert len(msgs) == 1                                   # mesma resposta: nada ajuda quem adivinha
    st = {t["name"]: t["status"] for t in client.get("/v1/enrollment-tokens", headers=world.user("admin")).json()}
    assert "piloto" in st


def test_only_admin_manages_tokens_and_tenants_are_isolated(client, world):
    assert client.post("/v1/enrollment-tokens", json={"name": "x"}, headers=world.user("analista")).status_code == 403
    t = make_token(client, world)
    enroll(client, t["token"])
    other = world.tok("admin@b.example.com")
    assert client.get("/v1/devices", headers=other).json()["devices"] == []
    assert client.get("/v1/enrollment-tokens", headers=other).json() == []
    dev_id = client.get("/v1/devices", headers=world.user("admin")).json()["devices"][0]["id"]
    assert client.post(f"/v1/devices/{dev_id}/revoke", headers=other).status_code == 404
    # o token é do tenant A: a chave que ele gera só enxerga o tenant A
    key = enroll(client, t["token"], host="NOTE-02").json()["api_key"]
    client.post("/v1/events", json=event("SIMULADO A"), headers={"X-API-Key": key})
    assert client.get("/v1/events", headers=other).json() == []


def test_enroll_validation_and_audit(client, world):
    assert client.post("/v1/enroll", json={}).status_code == 422
    t = make_token(client, world)
    assert client.post("/v1/enroll", json={"token": t["token"], "hostname": "A", "extra": 1}).status_code == 422
    enroll(client, t["token"], host="AUDITADO")
    acts = {a["action"] for a in client.get("/v1/audit-log", headers=world.user("auditor")).json()}
    assert {"enrollment_token.create", "device.enroll"} <= acts
