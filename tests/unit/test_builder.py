import json

from core.builder import build


def test_claude_md_always_included():
    files = build("# Hello", [], [])
    assert files["CLAUDE.md"] == "# Hello"


def test_biblioteca_agent_resolved_from_template():
    files = build("", [{"name": "test-writer", "source": "biblioteca", "conteudo": None}], [])
    assert ".claude/agents/test-writer.md" in files
    assert "test-writer" in files[".claude/agents/test-writer.md"]


def test_biblioteca_agent_missing_template_falls_back_to_conteudo():
    files = build(
        "",
        [{"name": "nonexistent-xyz", "source": "biblioteca", "conteudo": "# fallback"}],
        [],
    )
    assert files[".claude/agents/nonexistent-xyz.md"] == "# fallback"


def test_biblioteca_agent_missing_template_no_conteudo_skipped():
    files = build(
        "",
        [{"name": "nonexistent-xyz", "source": "biblioteca", "conteudo": None}],
        [],
    )
    assert ".claude/agents/nonexistent-xyz.md" not in files


def test_novo_agent_with_content():
    files = build(
        "",
        [{"name": "my-agent", "source": "novo", "conteudo": "# my-agent\nDoes things."}],
        [],
    )
    assert files[".claude/agents/my-agent.md"] == "# my-agent\nDoes things."


def test_novo_agent_empty_conteudo_skipped():
    files = build("", [{"name": "my-agent", "source": "novo", "conteudo": ""}], [])
    assert ".claude/agents/my-agent.md" not in files


def test_agent_name_with_traversal_normalized():
    files = build(
        "",
        [{"name": "../../etc/passwd", "source": "novo", "conteudo": "# evil"}],
        [],
    )
    agent_paths = [k for k in files if k.startswith(".claude/agents/")]
    assert agent_paths == [".claude/agents/etc-passwd.md"]


def test_agent_name_strange_chars_normalized():
    files = build(
        "",
        [{"name": "my agent!!v2", "source": "novo", "conteudo": "# x"}],
        [],
    )
    assert ".claude/agents/my-agent-v2.md" in files


def test_agent_name_empty_skipped():
    files = build("", [{"name": "", "source": "novo", "conteudo": "# x"}], [])
    assert not any(k.startswith(".claude/agents/") for k in files)


def test_agent_name_only_invalid_chars_skipped():
    files = build("", [{"name": "../..", "source": "novo", "conteudo": "# x"}], [])
    assert not any(k.startswith(".claude/agents/") for k in files)


def test_agents_section_appended_when_missing():
    agente = {
        "name": "test-writer",
        "source": "novo",
        "conteudo": "---\ndescription: Escreve testes pytest\n---\n# test-writer",
    }
    files = build("# Projeto", [agente], [])
    assert "## Agentes" in files["CLAUDE.md"]
    assert "**test-writer** — Escreve testes pytest" in files["CLAUDE.md"]


def test_agents_section_preserved_when_present():
    claude_md = "# Projeto\n\n## Agentes\n\n- já documentado\n"
    agente = {"name": "x", "source": "novo", "conteudo": "# x\nFaz algo."}
    files = build(claude_md, [agente], [])
    assert files["CLAUDE.md"] == claude_md
    assert files["CLAUDE.md"].count("## Agentes") == 1


def test_no_agents_section_without_agents():
    files = build("# Projeto", [], [])
    assert "## Agentes" not in files["CLAUDE.md"]


def test_primeiro_prompt_writes_prompt_and_launch_script():
    files = build("# md", [], [], "Comece implementando o módulo X")
    assert files[".claude/primeiro-prompt.txt"] == "Comece implementando o módulo X"
    assert "claude" in files[".claude/launch.sh"]
    assert "primeiro-prompt.txt" in files[".claude/launch.sh"]


def test_no_primeiro_prompt_no_launch_files():
    files = build("# md", [], [])
    assert ".claude/primeiro-prompt.txt" not in files
    assert ".claude/launch.sh" not in files


def test_plano_writes_build_file():
    plano = [
        {"ordem": 1, "task": "modelo de dados", "agente": None, "modelo": "opus",
         "contrato": "dataclass Chamado", "depende_de": []},
        {"ordem": 2, "task": "triagem bancos", "agente": "triagem-bancos",
         "modelo": "sonnet", "contrato": "", "depende_de": [1]},
    ]
    files = build("# md", [], [], "prompt", plano)
    conteudo = files[".claude/plano-build.md"]
    assert "modelo de dados" in conteudo
    assert "triagem-bancos" in conteudo
    assert "depende de: 1" in conteudo


def test_no_plano_no_build_file():
    files = build("# md", [], [], "prompt")
    assert ".claude/plano-build.md" not in files


def test_no_hooks_no_settings_json():
    files = build("# md", [], [])
    assert ".claude/settings.json" not in files


def test_hooks_produce_settings_json():
    files = build(
        "",
        [],
        [{"tipo": "PreToolUse", "matcher": "Bash", "script": "echo hi", "motivo": "x"}],
    )
    assert ".claude/settings.json" in files
    settings = json.loads(files[".claude/settings.json"])
    assert "PreToolUse" in settings["hooks"]
    entry = settings["hooks"]["PreToolUse"][0]
    assert entry["matcher"] == "Bash"
    assert entry["hooks"][0]["type"] == "command"


def test_null_matcher_excluded_from_settings():
    files = build(
        "",
        [],
        [{"tipo": "Stop", "matcher": None, "script": "echo bye", "motivo": "cleanup"}],
    )
    settings = json.loads(files[".claude/settings.json"])
    entry = settings["hooks"]["Stop"][0]
    assert "matcher" not in entry


def test_string_null_matcher_excluded():
    files = build(
        "",
        [],
        [{"tipo": "Stop", "matcher": "null", "script": "echo bye", "motivo": "x"}],
    )
    settings = json.loads(files[".claude/settings.json"])
    assert "matcher" not in settings["hooks"]["Stop"][0]


def test_hook_script_file_written():
    files = build(
        "",
        [],
        [
            {
                "tipo": "PreToolUse",
                "matcher": "Bash",
                "script": "#!/bin/bash\necho hi",
                "motivo": "x",
            }
        ],
    )
    hook_files = [k for k in files if k.startswith(".claude/hooks/")]
    assert len(hook_files) == 1
    assert files[hook_files[0]] == "#!/bin/bash\necho hi"


def test_multiple_hooks_separate_scripts():
    files = build(
        "",
        [],
        [
            {"tipo": "PreToolUse", "matcher": "Bash", "script": "s1", "motivo": "x"},
            {"tipo": "PostToolUse", "matcher": "Write", "script": "s2", "motivo": "y"},
        ],
    )
    hook_files = [k for k in files if k.startswith(".claude/hooks/")]
    assert len(hook_files) == 2


def test_hook_script_path_referenced_in_settings():
    files = build(
        "",
        [],
        [{"tipo": "PreToolUse", "matcher": "Bash", "script": "echo x", "motivo": "x"}],
    )
    settings = json.loads(files[".claude/settings.json"])
    command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert ".claude/hooks/" in command


# ── Tier de modelo no frontmatter do agente (vindo do plano) ─────────────────


def test_agent_frontmatter_gets_model_from_plano():
    agent = {"name": "esp", "source": "novo",
             "conteudo": "---\nname: esp\ndescription: faz X\n---\n# esp"}
    plano = [{"ordem": 1, "task": "y", "agente": "esp", "modelo": "opus", "depende_de": []}]
    files = build("# md", [agent], [], None, plano)
    conteudo = files[".claude/agents/esp.md"]
    assert "model: opus" in conteudo
    assert conteudo.startswith("---")  # frontmatter preservado


def test_free_tier_maps_to_haiku():
    agent = {"name": "mec", "source": "novo",
             "conteudo": "---\nname: mec\ndescription: boilerplate\n---\nbody"}
    plano = [{"ordem": 1, "task": "y", "agente": "mec", "modelo": "free", "depende_de": []}]
    files = build("", [agent], [], None, plano)
    assert "model: haiku" in files[".claude/agents/mec.md"]


def test_agent_without_plano_keeps_no_model():
    agent = {"name": "esp", "source": "novo",
             "conteudo": "---\nname: esp\ndescription: faz X\n---\nbody"}
    files = build("", [agent], [])
    assert "model:" not in files[".claude/agents/esp.md"]


def test_agent_no_frontmatter_unchanged_by_model():
    agent = {"name": "esp", "source": "novo", "conteudo": "# esp\nsem frontmatter"}
    plano = [{"ordem": 1, "task": "y", "agente": "esp", "modelo": "opus", "depende_de": []}]
    files = build("", [agent], [], None, plano)
    assert files[".claude/agents/esp.md"] == "# esp\nsem frontmatter"
