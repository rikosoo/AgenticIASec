"""Instalação em nível de máquina, em pasta de teste (--root). Nada toca /etc nem C:\\ProgramData reais."""
import json

from promptshield_claude_hook import deploy, setup


def test_refuses_without_employee_notice_confirmation(capsys, tmp_path):
    assert deploy.main(["--api-url", "http://x", "--token", "pse_x", "--root", str(tmp_path)]) == 2
    assert "avisados" in capsys.readouterr().out


def test_unknown_tool_is_rejected(tmp_path):
    assert deploy.main(["--api-url", "http://x", "--token", "pse_x", "--tools", "codex", "--confirm-employees-notified", "--root", str(tmp_path)]) == 2


def test_install_is_idempotent_keeps_foreign_settings_and_uninstall_is_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(deploy, "enroll", lambda url, token, tools: {"api_key": "ps_maquina1"})
    monkeypatch.setattr(deploy.client, "get_hook_config", lambda cfg: {"failure_mode": "open"})
    p = deploy.paths(tmp_path)
    p["claude"].parent.mkdir(parents=True)
    p["claude"].write_text(json.dumps({"model": "x", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "meu"}]}]}}))
    out = []
    for _ in range(2):
        assert deploy.install("http://localhost:8000/", "pse_t", list(deploy.ALL_TOOLS), "TI", "open", tmp_path, False, say=out.append) == 0
    assert any("já está matriculada" in o for o in out)
    cfg = json.loads(p["config"].read_text())
    assert cfg["api_key"] == "ps_maquina1" and cfg["api_url"] == "http://localhost:8000" and cfg["department"] == "TI"
    data = json.loads(p["claude"].read_text())
    assert data["model"] == "x" and setup.is_installed(data)
    assert sum(1 for g in data["hooks"]["PreToolUse"] for h in g["hooks"] if h.get("command") == "meu") == 1
    assert json.loads(p["copilot"].read_text())["version"] == 1
    deploy.uninstall(tmp_path, say=out.append)
    left = json.loads(p["claude"].read_text())
    assert not setup.is_installed(left) and left["model"] == "x" and "meu" in json.dumps(left)
    assert not p["config"].exists() and not p["copilot"].exists()


def test_failed_enrollment_changes_nothing(tmp_path, monkeypatch):
    def boom(url, token, tools):
        raise deploy.client.ApiError("recusada", status=401)
    monkeypatch.setattr(deploy, "enroll", boom)
    assert deploy.install("http://x", "pse_ruim", ["claude_code"], None, "open", tmp_path, False, say=lambda *_: None) == 1
    assert not any(tmp_path.rglob("*.json"))


def test_browser_extension_is_opt_in():
    assert "browser_extension" not in deploy.DEFAULT_TOOLS and "browser_extension" in deploy.ALL_TOOLS
