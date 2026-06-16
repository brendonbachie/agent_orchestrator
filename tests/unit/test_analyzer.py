from unittest.mock import patch

import pytest

from core.analyzer import analyze
from utils.claude import ClaudeError

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


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path):
    # Cada teste começa com cache vazio (sempre miss), sem tocar o cache real.
    with patch("utils.analysis_cache._CACHE_DIR", tmp_path / "ac"):
        yield


@pytest.fixture
def mock_run():
    with patch("core.analyzer.run_prompt", side_effect=[_ANALYSIS, _AGENTES, _RESULTADO]) as m:
        yield m


def test_analyze_returns_expected_keys(mock_run):
    result = analyze("Uma API REST simples")
    assert {"claude_md", "agentes", "hooks", "primeiro_prompt"} <= set(result.keys())


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


def test_analyze_includes_recomendacao_simple_project(mock_run):
    # _ANALYSIS tem 1 área de especialização → não recomenda orquestrar.
    result = analyze("desc")
    assert result["recomendacao"]["orquestrar"] is False


def test_recomendacao_true_for_multiple_areas():
    analise_multi = {**_ANALYSIS, "precisa_especializacao": ["a", "b", "c"]}
    with patch("core.analyzer.run_prompt", side_effect=[analise_multi, _AGENTES, _RESULTADO]):
        result = analyze("desc complexa")
    assert result["recomendacao"]["orquestrar"] is True


def test_analyze_includes_plano_key(mock_run):
    result = analyze("desc")
    assert "plano" in result and isinstance(result["plano"], list)


def test_third_prompt_mentions_plano(mock_run):
    analyze("desc")
    third = mock_run.call_args_list[2][0][0].lower()
    assert "plano" in third


def test_third_prompt_forces_task_delegation(mock_run):
    analyze("desc")
    third_prompt = mock_run.call_args_list[2][0][0].lower()
    # o primeiro_prompt gerado precisa instruir delegação via subagente/Task,
    # não só "use o agente" — senão a delegação não dispara no build.
    assert "subagente" in third_prompt and "task" in third_prompt


def test_third_prompt_injects_testing_discipline(mock_run):
    analyze("desc")
    third_prompt = mock_run.call_args_list[2][0][0]
    # a contenção anti over-testing precisa estar no prompt que gera o claude_md e o
    # primeiro_prompt (que ABRE o subagente).
    assert "teste o essencial, sem exaustividade" in third_prompt


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


# ── Validação de schema ──────────────────────────────────────────────────────


def test_analyze_raises_when_claude_md_missing():
    bad = {"hooks": [], "primeiro_prompt": "x"}  # sem claude_md
    with patch("core.analyzer.run_prompt", side_effect=[_ANALYSIS, _AGENTES, bad]):
        with pytest.raises(ClaudeError, match="resultado"):
            analyze("desc")


def test_analyze_raises_when_response_not_object():
    with patch("core.analyzer.run_prompt", side_effect=[["lista", "errada"], _AGENTES, _RESULTADO]):
        with pytest.raises(ClaudeError, match="análise"):
            analyze("desc")


def test_analyze_ignores_extra_keys():
    extra = {**_RESULTADO, "campo_inventado": 123}
    with patch("core.analyzer.run_prompt", side_effect=[_ANALYSIS, _AGENTES, extra]):
        result = analyze("desc")
    assert result["claude_md"] == _RESULTADO["claude_md"]
    assert "campo_inventado" not in result


# ── Economia de tokens: modelo por chamada e cache ───────────────────────────


def test_analyze_uses_sonnet_only_for_analysis(mock_run):
    analyze("desc")
    models = [c.kwargs.get("model") for c in mock_run.call_args_list]
    # Sonnet só na análise (P1); agentes (P2) e artefato final (P3) em Opus.
    assert models == ["sonnet", "opus", "opus"]


def test_analyze_caches_identical_descricao():
    with patch(
        "core.analyzer.run_prompt", side_effect=[_ANALYSIS, _AGENTES, _RESULTADO]
    ) as m:
        first = analyze("uma descrição única")
        second = analyze("uma descrição única")
    assert m.call_count == 3  # segunda chamada veio do cache, sem novos prompts
    assert first == second


def test_analyze_cache_miss_on_different_descricao():
    side = [_ANALYSIS, _AGENTES, _RESULTADO, _ANALYSIS, _AGENTES, _RESULTADO]
    with patch("core.analyzer.run_prompt", side_effect=side) as m:
        analyze("descrição A")
        analyze("descrição B")
    assert m.call_count == 6  # descrições distintas → não compartilham cache
