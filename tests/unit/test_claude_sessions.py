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
