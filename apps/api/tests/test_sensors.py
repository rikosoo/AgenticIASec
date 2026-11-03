"""Painel de sensores: IAs escolhidas por máquina, atualização pelo próprio sensor e evidência (eventos) por IA. Dados SINTÉTICOS."""
from datetime import datetime, timedelta, timezone

import pytest
from conftest import event

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def _fresh_rate_limit():
    from app import ratelimit
    ratelimit.reset()


def token(client, world, who="admin"):
    return client.post("/v1/enrollment-tokens", json={"name": "piloto"}, headers=world.user(who)).json()["token"]


def enroll(client, tok, host, ias=(), tools=("claude_code",)):
    r = client.post("/v1/enroll", json={"token": tok, "hostname": host, "os": "windows", "client_version": "0.1", "tools": list(tools), "ias": list(ias)})
    assert r.status_code == 201, r.text
    return r.json()["api_key"]


def send(client, key, app, when=None, text="SIMULADO: oi"):
    ev = event(text, source={"channel": "browser" if app.endswith("_web") else "agent_hook", "app": app, "integration_status": "experimental"})
    if when:
        ev["occurred_at"] = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    r = client.post("/v1/events", json=ev, headers={"X-API-Key": key})
    assert r.status_code == 200, r.text


def devices(client, world, who="leitura"):
    return {d["hostname"]: d for d in client.get("/v1/devices", headers=world.user(who)).json()["devices"]}


def test_enrollment_stores_chosen_ias_and_validates_them(client, world):
    tok = token(client, world)
    enroll(client, tok, "NB-ANA", ias=["gemini_web", "chatgpt_web", "chatgpt_web", "claude_code"], tools=["claude_code", "browser_extension"])
    out = client.get("/v1/devices", headers=world.user("leitura")).json()
    d = out["devices"][0]
    assert d["hostname"] == "NB-ANA" and d["ias"] == ["chatgpt_web", "claude_code", "gemini_web"]          # ordenado, sem repetir
    assert out["ias_coverage"] == {"chatgpt_web": 1, "claude_code": 1, "gemini_web": 1}
    for bad in (["ChatGPT"], ["a"], ["x" * 41], ["com espaço"], [f"ia_{i}" for i in range(21)]):
        r = client.post("/v1/enroll", json={"token": tok, "hostname": "NB-X", "os": "windows", "tools": [], "ias": bad})
        assert r.status_code == 422, bad
    assert devices(client, world)["NB-ANA"]["ias"]                                                         # a recusa não gastou nem criou nada
    assert len(devices(client, world)) == 1


def test_a_sensor_can_report_its_ias_later_and_choices_accumulate_with_add(client, world):
    key = enroll(client, token(client, world), "NB-BIA")
    assert devices(client, world)["NB-BIA"]["ias"] == []
    h = {"X-API-Key": key}
    assert client.put("/v1/device/ias", json={"ias": ["claude_code"], "mode": "add"}, headers=h).json() == {"ias": ["claude_code"]}
    assert client.put("/v1/device/ias", json={"ias": ["gemini_web"], "mode": "add"}, headers=h).json() == {"ias": ["claude_code", "gemini_web"]}
    assert client.put("/v1/device/ias", json={"ias": ["claude_web"]}, headers=h).json() == {"ias": ["claude_web"]}      # padrão: substitui
    assert devices(client, world)["NB-BIA"]["ias"] == ["claude_web"]
    assert client.put("/v1/device/ias", json={"ias": ["Maiúscula"]}, headers=h).status_code == 422
    assert client.put("/v1/device/ias", json={"ias": [], "extra": 1}, headers=h).status_code == 422
    assert world.sql("SELECT count(*) FROM audit_log WHERE action = 'device.ias_update'").scalar() == 3


def test_only_a_device_key_can_report_and_nobody_else(client, world):
    assert client.put("/v1/device/ias", json={"ias": ["claude_code"]}, headers=world.key()).status_code == 404        # chave padrão do tenant não é máquina
    assert client.put("/v1/device/ias", json={"ias": ["claude_code"]}, headers=world.user("admin")).status_code == 403  # usuário do console não
    assert client.put("/v1/device/ias", json={"ias": ["claude_code"]}).status_code in (401, 403)
    key = enroll(client, token(client, world), "NB-CAIO")
    d = client.get("/v1/devices", headers=world.user("admin")).json()["devices"][0]
    client.post(f"/v1/devices/{d['id']}/revoke", headers=world.user("admin"))
    assert client.put("/v1/device/ias", json={"ias": ["claude_code"]}, headers={"X-API-Key": key}).status_code == 401  # chave revogada


def test_activity_per_sensor_and_app_is_real_evidence_and_not_mixed_between_sensors(client, world):
    now = datetime.now(timezone.utc)
    a = enroll(client, token(client, world), "NB-A", ias=["chatgpt_web", "claude_code"])
    b = enroll(client, token(client, world), "NB-B", ias=["chatgpt_web"])
    send(client, a, "chatgpt_web")
    send(client, a, "chatgpt_web")
    send(client, a, "claude_code", when=now - timedelta(days=10))               # fora dos 7 dias, dentro dos 30
    send(client, a, "gemini_web", when=now - timedelta(days=40))                # fora dos 30: não aparece
    send(client, b, "claude_code")
    assert client.post("/v1/events", json=event("SIMULADO: chave padrão do tenant"), headers=world.key()).status_code == 200   # sem sensor
    d = devices(client, world)
    act_a, act_b = d["NB-A"]["activity"], d["NB-B"]["activity"]
    assert act_a["chatgpt_web"]["events_7d"] == 2 and act_a["chatgpt_web"]["events_30d"] == 2 and act_a["chatgpt_web"]["last_at"]
    assert act_a["claude_code"]["events_7d"] == 0 and act_a["claude_code"]["events_30d"] == 1
    assert "gemini_web" not in act_a
    assert set(act_b) == {"claude_code"} and act_b["claude_code"]["events_7d"] == 1                        # o evento do B não vai para o A
    # o evento da chave padrão do tenant tem chave, mas nenhuma máquina: não aparece em sensor nenhum
    assert world.sql("SELECT count(*) FROM events e WHERE NOT EXISTS (SELECT 1 FROM devices d WHERE d.api_key_id = e.api_key_id)").scalar() == 1
