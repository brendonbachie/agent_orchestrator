import json
import re
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "agents"
_VALID_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


_LAUNCH_SCRIPT = """\
#!/usr/bin/env bash
# Abre o Claude Code no projeto com o primeiro prompt gerado pelo orquestrador.
# --model sonnet: o build roda no modelo barato (medimos ~5x vs Opus). O trabalho
# pesado vai para subagentes (que podem ter model próprio no frontmatter); para
# decisões realmente difíceis, suba com /model dentro da sessão.
cd "$(dirname "$0")/.." || exit 1
claude --model sonnet "$(cat .claude/primeiro-prompt.txt)"
"""


def build(
    claude_md: str,
    agentes: list[dict],
    hooks: list[dict],
    primeiro_prompt: str | None = None,
    plano: list[dict] | None = None,
) -> dict[str, str]:
    """Return {relative_path: content} for every file to be written to the project."""
    files: dict[str, str] = {}

    if primeiro_prompt:
        files[".claude/primeiro-prompt.txt"] = primeiro_prompt
        files[".claude/launch.sh"] = _LAUNCH_SCRIPT

    if plano:
        files[".claude/plano-build.md"] = _plano_md(plano)

    # Tier de modelo por agente, do plano (task.agente -> task.modelo): cada subagente
    # roda no seu preço (mecânico barato, crítico opus) quando o supervisor o abre via
    # Task. Medido: o Claude Code respeita o `model:` no frontmatter do agente.
    tier_por_agente: dict[str, str | None] = {}
    for t in plano or []:
        ag = t.get("agente")
        if ag and ag not in tier_por_agente:
            tier_por_agente[ag] = t.get("modelo")

    agent_files: list[tuple[str, str]] = []
    for agent in agentes:
        raw = agent.get("name")
        name = _normalize_name(raw)
        if not name:
            continue
        content = _resolve_agent(agent, name)
        if content:
            modelo = _tier_para_model(tier_por_agente.get(raw))
            if modelo:
                content = _inject_agent_model(content, modelo)
            files[f".claude/agents/{name}.md"] = content
            agent_files.append((name, content))

    files["CLAUDE.md"] = _ensure_agents_section(claude_md, agent_files)

    if hooks:
        hook_settings: dict[str, list] = {}

        for i, hook in enumerate(hooks):
            script_name = f"{hook['tipo'].lower()}-{i + 1}.sh"
            files[f".claude/hooks/{script_name}"] = hook["script"]

            tipo = hook["tipo"]
            if tipo not in hook_settings:
                hook_settings[tipo] = []

            entry: dict = {
                "hooks": [{"type": "command", "command": f"bash .claude/hooks/{script_name}"}]
            }
            matcher = hook.get("matcher")
            if matcher and str(matcher).lower() != "null":
                entry["matcher"] = matcher

            hook_settings[tipo].append(entry)

        files[".claude/settings.json"] = json.dumps(
            {"hooks": hook_settings}, indent=2, ensure_ascii=False
        )

    return files


def _plano_md(plano: list[dict]) -> str:
    """Formata o plano de tasks como `.claude/plano-build.md` para o build seguir."""
    linhas = [
        "# Plano de build",
        "",
        "Construa nesta ordem. Task pesada/especializada → abra um subagente (Task).",
        "O tier indica o modelo: free=mecânico, sonnet=padrão, opus=crítico.",
        "",
    ]
    for t in plano:
        linhas.append(f"## {t.get('ordem', '?')}. {t.get('task', '')}")
        linhas.append(f"- agente: {t.get('agente') or '—'} · modelo: {t.get('modelo', 'sonnet')}")
        if t.get("contrato"):
            linhas.append(f"- contrato: {t['contrato']}")
        deps = t.get("depende_de") or []
        if deps:
            linhas.append(f"- depende de: {', '.join(str(d) for d in deps)}")
        linhas.append("")
    return "\n".join(linhas)


def _ensure_agents_section(claude_md: str, agent_files: list[tuple[str, str]]) -> str:
    """Garante que o CLAUDE.md tenha uma seção '## Agentes' listando os subagentes.

    Sem essa seção o Claude Code até descobre os agentes em .claude/agents/,
    mas raramente delega para eles. Se o analyzer já gerou a seção, preserva.
    """
    if not agent_files or re.search(r"^##+\s*agentes", claude_md, re.IGNORECASE | re.MULTILINE):
        return claude_md

    linhas = [
        "",
        "## Agentes",
        "",
        "Delegue para os subagentes em `.claude/agents/` sempre que a tarefa corresponder:",
        "",
    ]
    for name, content in agent_files:
        desc = _agent_description(content)
        linhas.append(f"- **{name}** — {desc}" if desc else f"- **{name}**")

    return claude_md.rstrip() + "\n" + "\n".join(linhas) + "\n"


def _agent_description(content: str) -> str:
    """Extrai a descrição do agente: frontmatter `description:` ou primeira linha de texto."""
    lines = content.strip().splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break
            if stripped.startswith("description:"):
                return stripped.removeprefix("description:").strip().strip("\"'")
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "---")):
            return stripped
    return ""


def _normalize_name(name: str | None) -> str | None:
    """Return a filesystem-safe agent name, or None if nothing usable remains."""
    if not name:
        return None
    if _VALID_NAME.fullmatch(name):
        return name
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", name)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or None


def _resolve_agent(agent: dict, name: str) -> str | None:
    if agent.get("source") == "biblioteca":
        template = _TEMPLATES_DIR / f"{name}.md"
        if template.exists():
            return template.read_text(encoding="utf-8")
    content = agent.get("conteudo")
    return content if content else None
