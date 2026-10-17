"""Escolha das IAs por números. Nada aqui toca arquivos reais do usuário."""
import json

import pytest

from promptshield_claude_hook import deploy, ias, setup

NAMES = ["ChatGPT", "Copilot (web", "Gemini", "Codex (app desktop)", "Claude (app desktop)", "Claude Code", "Codex (CLI)", "Copilot (app desktop)"]


def test_the_eight_requested_options_are_in_the_list_in_order():
    text = ias.render_list()
    for i, name in enumerate(NAMES, 1):
        assert any(line.strip().startswith(f"{i})") and name in line for line in text.splitlines()), (i, name)
    assert "separados por vírgula" in text


@pytest.mark.parametrize("raw,expected", [("1,2,6", [1, 2, 6]), (" 6 , 1 ,1", [1, 6]), ("1;3", [1, 3]), ("todas", list(range(1, 11))), ("TODAS", list(range(1, 11)))])
def test_parse_accepts_commas_spaces_and_all(raw, expected):
    assert ias.parse_selection(raw) == (expected, [])


@pytest.mark.parametrize("raw", ["", "abc", "1,x", "0", "11", "1,99", "1.5"])
def test_parse_rejects_bad_input_with_a_message(raw):
    nums, errs = ias.parse_selection(raw)
    assert nums == [] and errs


def test_every_option_has_an_honest_state_and_a_guide_and_manual_ones_do_not_auto_install():
    assert {i.state for i in ias.CATALOG} <= {ias.AUTO, ias.EXT, ias.MANUAL, ias.NONE}
    for i in ias.CATALOG:
        assert i.status and ias.guide(i.n)
    for n in (4, 7, 8):                                    # Codex (desktop e CLI) e Copilot desktop: nada é instalado sozinho
        assert ias.BY_N[n].state != ias.AUTO and ias.BY_N[n].tool is None
    assert "A VERIFICAR" in ias.BY_N[7].status and "A VERIFICAR" in ias.BY_N[4].status
    assert ias.tools_for([1, 2, 3, 10]) == ["browser_extension"] and ias.tools_for([6, 5, 1]) == ["claude_code", "browser_extension"]
    assert ias.tools_for([4, 7, 8]) == []


def test_wizard_choice_flow_configures_only_what_is_automatic(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot"))
    monkeypatch.setattr(setup.Path, "home", classmethod(lambda cls: tmp_path))
    for k in ("PROMPTSHIELD_HOOK_CONFIG", "PROMPTSHIELD_API_URL", "PROMPTSHIELD_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    setup.write_hook_config("http://localhost:8000", "ps_x")
    monkeypatch.setattr("promptshield_claude_hook.client.get_hook_config", lambda cfg: {"failure_mode": "open"})
    prepared = []
    monkeypatch.setattr(setup.browser, "install_extension", lambda *a, **k: prepared.append(a) or tmp_path)
    out, answers = [], iter(["6, 7 ,8, 1", "sim", "0"])
    w = setup.Wizard(ask=lambda p: next(answers), secret=lambda p: "", say=lambda *x: out.append(" ".join(map(str, x))), open_url=lambda u: None)
    w.choose()
    text = "\n".join(out)
    assert setup.is_installed(setup.read_settings(setup.claude_settings_path()))        # 6: automático
    assert prepared and not setup.copilot_hooks_path().exists()                        # 1: extensão preparada; Copilot CLI não foi pedido
    assert "[7] Codex (CLI): MANUAL" in text and "[8] Copilot (app desktop): INDISPONÍVEL" in text and "Resumo" in text
    assert "extensão" in text.lower()


def test_wizard_choice_reasks_on_bad_input_and_gives_up_after_three(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.Path, "home", classmethod(lambda cls: tmp_path))
    out, answers = [], iter(["x", "99", ""])
    w = setup.Wizard(ask=lambda p: next(answers), secret=lambda p: "", say=lambda *x: out.append(" ".join(map(str, x))), open_url=lambda u: None)
    w.choose()
    assert "Nada selecionado." in "\n".join(out)


def test_deploy_ias_flag_prints_guides_and_maps_tools(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(deploy, "enroll", lambda url, token, tools: {"api_key": "ps_m"})
    monkeypatch.setattr(deploy.client, "get_hook_config", lambda cfg: {"failure_mode": "open"})
    monkeypatch.setattr(deploy.browser, "install_extension", lambda *a, **k: tmp_path)
    assert deploy.main(["--list-ias"]) == 0 and "Quais IAs" in capsys.readouterr().out
    rc = deploy.main(["--api-url", "http://x", "--token", "pse_t", "--ias", "6,7", "--confirm-employees-notified", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0 and "[7] Codex (CLI): MANUAL" in out and "[6] Claude Code (CLI, terminal): AUTOMÁTICO" in out
    p = deploy.paths(tmp_path)
    assert setup.is_installed(json.loads(p["claude"].read_text())) and not p["copilot"].exists()
    assert deploy.main(["--api-url", "http://x", "--token", "pse_t", "--ias", "0", "--confirm-employees-notified", "--root", str(tmp_path)]) == 2


def test_docs_list_every_option():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[4] / "docs" / "guia-ias.md").read_text(encoding="utf-8")
    for i in ias.CATALOG:
        assert f"| {i.n} |" in doc and i.name.split(" (")[0] in doc, i.name
