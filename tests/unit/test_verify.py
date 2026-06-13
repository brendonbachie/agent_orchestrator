from unittest.mock import MagicMock, patch

from utils.verify import run_pytest


def _proc(returncode):
    r = MagicMock()
    r.returncode = returncode
    return r


def test_passa_quando_testes_passam():
    with patch("subprocess.run", return_value=_proc(0)):
        assert run_pytest("/p") is True


def test_passa_quando_nao_ha_testes():
    with patch("subprocess.run", return_value=_proc(5)):
        assert run_pytest("/p") is True


def test_falha_quando_testes_falham():
    with patch("subprocess.run", return_value=_proc(1)):
        assert run_pytest("/p") is False


def test_erro_de_colecao_nao_bloqueia():
    with patch("subprocess.run", return_value=_proc(2)):
        assert run_pytest("/p") is True


def test_pytest_ausente_nao_bloqueia():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        assert run_pytest("/p") is True
