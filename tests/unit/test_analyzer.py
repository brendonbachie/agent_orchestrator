from unittest.mock import patch

import pytest

from core.analyzer import analyze

_ANALYSIS = {
    "stack": ["Python", "FastAPI"],
    "padrao": "api",
    "pontos_de_falha": ["timeout"],
    "precisa_especializacao": ["testes"],
}

_AGENTES = {
    "agentes": [{"name": "test-writer", "source": "biblioteca", "conteudo": None}]
}

_RESULTADO = {
    "hooks": [{"tipo": "PreToolUse", "matcher": "Bash", "script": "echo x", "motivo": "y"}],
    "primeiro_prompt": "Comece aqui",
    "claude_md": "# Projeto\n\nStack: Python\n",
}


@pytest.fixture
def mock_run():
    with patch("core.analyzer.run_prompt", side_effect=[_ANALYSIS, _AGENTES, _RESULTADO]) as m:
        yield m


def test_analyze_returns_expected_keys(mock_run):
    result = analyze("Uma API REST simples")
    assert set(result.keys()) == {"claude_md", "agentes", "hooks", "primeiro_prompt"}


def test_analyze_calls_run_prompt_three_times(mock_run):
    analyze("desc")
    assert mock_run.call_count == 3


def test_analyze_passes_descricao_to_first_prompt(mock_run):
    analyze("minha descrição única")
    first_prompt = mock_run.call_args_list[0][0][0]
    assert "minha descrição única" in first_prompt


def test_analyze_passes_analysis_to_second_prompt(mock_run):
    analyze("desc")
    second_prompt = mock_run.call_args_list[1][0][0]
    assert "FastAPI" in second_prompt or "Python" in second_prompt


def test_analyze_passes_agents_to_third_prompt(mock_run):
    analyze("desc")
    third_prompt = mock_run.call_args_list[2][0][0]
    assert "test-writer" in third_prompt


def test_analyze_passes_template_list_to_second_prompt(mock_run):
    analyze("desc")
    second_prompt = mock_run.call_args_list[1][0][0]
    # template names should be in the prompt
    assert "test-writer" in second_prompt or "readme-generator" in second_prompt


def test_analyze_returns_agentes_from_second_prompt(mock_run):
    result = analyze("desc")
    assert result["agentes"] == _AGENTES["agentes"]


def test_analyze_returns_hooks_from_third_prompt(mock_run):
    result = analyze("desc")
    assert result["hooks"] == _RESULTADO["hooks"]


def test_analyze_returns_claude_md_from_third_prompt(mock_run):
    result = analyze("desc")
    assert result["claude_md"] == _RESULTADO["claude_md"]
