from unittest.mock import patch

from utils.claude_sessions import (
    encode_session_dirname,
    read_session_jsonl,
    to_wsl_path,
)


def test_to_wsl_path_converts_windows_drive():
    assert to_wsl_path("C:\\Users\\x\\proj") == "/mnt/c/Users/x/proj"


def test_to_wsl_path_forward_slashes():
    assert to_wsl_path("D:/foo/bar") == "/mnt/d/foo/bar"


def test_to_wsl_path_passes_through_non_windows():
    assert to_wsl_path("/already/posix") == "/already/posix"


def test_encode_session_dirname_basic():
    assert encode_session_dirname("/mnt/c/Users/x/proj") == "-mnt-c-Users-x-proj"


def test_encode_session_dirname_matches_claude_rule():
    # Caso real verificado: espaços e acentos viram '-', sem colapsar.
    wsl = "/mnt/c/Users/brend/OneDrive/Área de Trabalho/Projetos/chamados-cp"
    esperado = "-mnt-c-Users-brend-OneDrive--rea-de-Trabalho-Projetos-chamados-cp"
    assert encode_session_dirname(wsl) == esperado


def test_read_session_jsonl_includes_subagents(tmp_path):
    # Branch POSIX: deve concatenar a sessão principal E os transcripts de subagente
    # (subpasta `*/subagents/`), senão o consumo fica subestimado (cegueira de sidechain).
    pasta_wsl = "/mnt/c/proj/x"
    encoded = encode_session_dirname(pasta_wsl)
    base = tmp_path / ".claude" / "projects" / encoded
    (base / "sess" / "subagents").mkdir(parents=True)
    (base / "sess.jsonl").write_text('{"main": 1}\n', encoding="utf-8")
    (base / "sess" / "subagents" / "agent-1.jsonl").write_text('{"sub": 1}\n', encoding="utf-8")

    with patch("utils.claude_sessions._ON_WINDOWS", False), \
         patch("utils.claude_sessions.Path.home", return_value=tmp_path):
        text = read_session_jsonl(pasta_wsl)

    assert '{"main": 1}' in text
    assert '{"sub": 1}' in text


def test_read_session_jsonl_missing_returns_empty(tmp_path):
    with patch("utils.claude_sessions._ON_WINDOWS", False), \
         patch("utils.claude_sessions.Path.home", return_value=tmp_path):
        assert read_session_jsonl("/mnt/c/nada") == ""
