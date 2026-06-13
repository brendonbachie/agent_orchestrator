import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from utils.claude import ClaudeError, run_prompt, run_task


def _proc(stdout="", returncode=0, stderr=""):
    r = MagicMock()
    r.stdout = stdout
    r.returncode = returncode
    r.stderr = stderr
    return r


def test_run_prompt_returns_parsed_json():
    with patch("subprocess.run", return_value=_proc('{"key": "value"}')):
        result = run_prompt("test prompt")
    assert result == {"key": "value"}


def test_strips_markdown_fences_json_tag():
    with patch("subprocess.run", return_value=_proc('```json\n{"a": 1}\n```')):
        assert run_prompt("test") == {"a": 1}


def test_strips_markdown_fences_no_tag():
    with patch("subprocess.run", return_value=_proc('```\n{"b": 2}\n```')):
        assert run_prompt("test") == {"b": 2}


def test_strips_fences_without_closing():
    with patch("subprocess.run", return_value=_proc('```json\n{"c": 3}')):
        assert run_prompt("test") == {"c": 3}


def test_prose_before_and_after_json():
    out = 'Aqui está o JSON: {"key": "value"} Espero que ajude!'
    with patch("subprocess.run", return_value=_proc(out)):
        assert run_prompt("test") == {"key": "value"}


def test_nested_json_followed_by_text():
    out = '{"a": {"b": [1, 2], "c": "x}y"}} obrigado pela atenção'
    with patch("subprocess.run", return_value=_proc(out)):
        assert run_prompt("test") == {"a": {"b": [1, 2], "c": "x}y"}}


def test_fence_with_prose_outside():
    out = 'Segue o resultado:\n```json\n{"d": 4}\n```\nQualquer dúvida, avise!'
    with patch("subprocess.run", return_value=_proc(out)):
        assert run_prompt("test") == {"d": 4}


def test_raises_when_output_is_json_list():
    with patch("subprocess.run", return_value=_proc("[1, 2, 3]")):
        with pytest.raises(ClaudeError, match="expected an object"):
            run_prompt("test")


def test_raises_on_empty_output():
    with patch("subprocess.run", return_value=_proc("")):
        with pytest.raises(ClaudeError, match="non-JSON"):
            run_prompt("test")


def test_raises_on_nonzero_exit():
    with patch("subprocess.run", return_value=_proc("", returncode=1, stderr="bad")):
        with pytest.raises(ClaudeError, match="exited 1"):
            run_prompt("test")


def test_raises_on_invalid_json():
    with patch("subprocess.run", return_value=_proc("not json at all")):
        with pytest.raises(ClaudeError, match="non-JSON"):
            run_prompt("test")


def test_raises_when_claude_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        with pytest.raises(ClaudeError, match="not found"):
            run_prompt("test")


def test_raises_on_timeout():
    with patch(
        "subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 60)
    ):
        with pytest.raises(ClaudeError, match="timed out"):
            run_prompt("test")


# ── run_task (runner do dispatcher) ──────────────────────────────────────────


def test_run_task_returns_usage_and_cost(tmp_path):
    envelope = json.dumps(
        {"is_error": False, "usage": {"output_tokens": 5}, "total_cost_usd": 0.01, "num_turns": 3}
    )
    with patch("subprocess.run", return_value=_proc(envelope)):
        r = run_task("faça X", "sonnet", str(tmp_path))
    assert r["ok"] is True
    assert r["usage"]["output_tokens"] == 5
    assert r["cost_usd"] == 0.01
    assert r["num_turns"] == 3


def test_run_task_raises_on_nonzero_exit(tmp_path):
    with patch("subprocess.run", return_value=_proc("", returncode=1, stderr="boom")):
        with pytest.raises(ClaudeError, match="exited 1"):
            run_task("x", "sonnet", str(tmp_path))


# ── Hardening: stdin, allowlist de modelo, validação de cwd ───────────────────


def test_run_prompt_passes_prompt_via_stdin_not_argv():
    """O prompt vai por stdin; nunca aparece no argv (anti argument-injection)."""
    mock = MagicMock(return_value=_proc('{"ok": 1}'))
    with patch("subprocess.run", mock):
        run_prompt("--dangerously-skip-permissions e mais texto")
    args, kwargs = mock.call_args
    assert kwargs["input"] == "--dangerously-skip-permissions e mais texto"
    assert "--dangerously-skip-permissions e mais texto" not in args[0]


def test_run_prompt_rejects_unknown_model():
    with patch("subprocess.run", return_value=_proc('{"ok": 1}')) as mock:
        with pytest.raises(ClaudeError, match="modelo não permitido"):
            run_prompt("x", model="--dangerously-skip-permissions")
    mock.assert_not_called()


def test_run_prompt_allows_known_model():
    mock = MagicMock(return_value=_proc('{"ok": 1}'))
    with patch("subprocess.run", mock):
        run_prompt("x", model="opus")
    argv = mock.call_args.args[0]
    assert "--model" in argv and "opus" in argv


def test_run_task_free_tier_maps_to_sonnet(tmp_path):
    """O tier "free" (#12 ainda sem roteamento) cai no sonnet em vez de quebrar."""
    mock = MagicMock(return_value=_proc('{"is_error": false, "usage": {}}'))
    with patch("subprocess.run", mock):
        run_task("x", "free", str(tmp_path))
    argv = mock.call_args.args[0]
    assert argv[argv.index("--model") + 1] == "sonnet"


def test_run_task_rejects_unknown_model(tmp_path):
    with patch("subprocess.run") as mock:
        with pytest.raises(ClaudeError, match="modelo não permitido"):
            run_task("x", "--evil-flag", str(tmp_path))
    mock.assert_not_called()


def test_run_task_rejects_nonexistent_cwd():
    with patch("subprocess.run") as mock:
        with pytest.raises(ClaudeError, match="cwd inválido"):
            run_task("x", "sonnet", "/nao/existe/mesmo/12345")
    mock.assert_not_called()
