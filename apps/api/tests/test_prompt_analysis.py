"""Análise de prompts: filtros novos, sinais agregados e detalhe com trechos. Dados SINTÉTICOS."""
import pytest
from conftest import event

pytestmark = pytest.mark.db

SECRET = "AKIAZ7QW4XK2M9PLR3TN"


def post(client, world, text, **over):
    r = client.post("/v1/events", json=event(text, **over), headers=world.key())
    assert r.status_code == 200, r.text
    return r.json()


def tool(client, world, name, command):
    ev = event("", kind="tool_call")
    ev["content"] = {"tool_name": name, "tool_input": {"command": command}}
    assert client.post("/v1/events", json=ev, headers=world.key()).status_code == 200


def listing(client, world, **params):
    return client.get("/v1/events", params={"days": 365, **params}, headers=world.user("leitura")).json()


def test_filters_by_kind_text_span_type_and_intent(client, world):
    post(client, world, f"SIMULADO: revise meu deploy, a chave é {SECRET}")
    post(client, world, "SIMULADO: resuma este texto sobre café")
    post(client, world, "SIMULADO: o código é confidencial, queria melhorar")
    tool(client, world, "PowerShell", "Get-Content $HOME\\.aws\\credentials")

    assert {e["kind"] for e in listing(client, world, kind="tool_call")} == {"tool_call"}
    assert len(listing(client, world, kind="prompt")) == 3
    assert len(listing(client, world, q="café")) == 1
    assert len(listing(client, world, q="%%")) == 0                                  # % e _ são literais, não curingas
    assert SECRET not in str(listing(client, world))                                # a busca e a lista só veem texto mascarado
    assert len(listing(client, world, span_type="aws_access_key")) == 1
    assert len(listing(client, world, intent="resumir")) == 1
    assert len(listing(client, world, intent="declara_confidencial")) == 1
    assert len(listing(client, world, intent="revisar_corrigir")) == 1


def test_detail_has_spans_tool_name_and_session_but_no_original(client, world):
    post(client, world, f"SIMULADO: chave {SECRET}")
    tool(client, world, "PowerShell", "Get-Content $HOME\\.aws\\credentials")
    rows = {e["kind"]: e for e in listing(client, world)}
    assert rows["tool_call"]["tool_name"] == "PowerShell" and rows["tool_call"]["masked_text"].startswith("Get-Content")
    assert rows["prompt"]["session_id"] == "s1"
    spans = rows["prompt"]["spans"]
    assert any(sp["type"] == "aws_access_key" for sp in spans) and SECRET not in str(spans)
    assert rows["prompt"]["flags"]["intents"] == []


def test_signals_are_counts_only(client, world):
    post(client, world, f"SIMULADO: chave {SECRET} e outra {SECRET}")
    post(client, world, "SIMULADO: traduza isto")
    tool(client, world, "PowerShell", "ls")
    sg = client.get("/v1/stats/signals", headers=world.user("leitura")).json()
    assert sg["span_types"].get("aws_access_key") == 1                                     # um evento conta uma vez, mesmo com dois trechos
    assert sg["intents"].get("traduzir") == 1 and sg["kinds"] == {"prompt": 2, "tool_call": 1} and sg["tools"] == {"PowerShell": 1}
    assert SECRET not in str(sg)
    other = client.get("/v1/stats/signals", headers=world.tok("admin@b.example.com")).json()
    assert other == {"span_types": {}, "intents": {}, "kinds": {}, "tools": {}}      # isolamento por tenant
