import json
from pathlib import Path

from utils.claude import run_prompt

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "agents"

_PROMPT_1 = """Analisa esse projeto e retorna APENAS JSON válido, sem markdown, sem explicação:
{{
  "stack": ["linguagem", "frameworks", "ferramentas"],
  "padrao": "cli|api|daemon|web|lambda|biblioteca",
  "pontos_de_falha": ["lista dos riscos principais"],
  "precisa_especializacao": ["áreas que precisam de agente dedicado"]
}}

Projeto: {descricao}"""

_PROMPT_2 = """Dado essa análise de projeto:
{analise}

Biblioteca de agentes disponíveis: {lista_templates}

Para cada área de especialização identificada, decide se existe um agente adequado
na biblioteca ou se é necessário criar um novo.
Retorna APENAS JSON válido, sem markdown, sem explicação:
{{
  "agentes": [
    {{
      "name": "nome-do-agente",
      "source": "biblioteca|novo",
      "conteudo": "conteúdo completo em markdown se source=novo, null se source=biblioteca"
    }}
  ]
}}"""

_PROMPT_3 = """Projeto: {descricao}
Análise: {analise}
Agentes planejados: {agentes}

Retorna APENAS JSON válido, sem markdown, sem explicação:
{{
  "hooks": [
    {{
      "tipo": "PreToolUse|PostToolUse|Stop",
      "matcher": "Bash|Write|null",
      "script": "conteúdo completo do script bash",
      "motivo": "por que esse hook é necessário para esse projeto"
    }}
  ],
  "primeiro_prompt": "primeiro prompt para enviar ao Claude Code e iniciar o projeto",
  "claude_md": "CLAUDE.md completo: visão geral, stack, estrutura, convenções e comandos"
}}

Regras para o claude_md:
- DEVE incluir uma seção "## Agentes" listando cada agente planejado, com uma linha
  no formato "use o agente <nome> para <quando usar>" — é por essa seção que o
  Claude Code saberá quando delegar trabalho aos agentes em .claude/agents/.
- Mencione os hooks configurados e o que eles bloqueiam/verificam.

O primeiro_prompt deve citar pelo nome os agentes relevantes para a primeira tarefa."""


def _list_templates() -> list[str]:
    return sorted(p.stem for p in _TEMPLATES_DIR.glob("*.md"))


def analyze(descricao: str) -> dict:
    templates = _list_templates()

    analise = run_prompt(_PROMPT_1.format(descricao=descricao), timeout=180)

    agentes_raw = run_prompt(
        _PROMPT_2.format(
            analise=json.dumps(analise, ensure_ascii=False),
            lista_templates=json.dumps(templates, ensure_ascii=False),
        ),
        timeout=180,
    )

    resultado = run_prompt(
        _PROMPT_3.format(
            descricao=descricao,
            analise=json.dumps(analise, ensure_ascii=False),
            agentes=json.dumps(agentes_raw.get("agentes", []), ensure_ascii=False),
        ),
        timeout=180,
    )

    return {
        "claude_md": resultado["claude_md"],
        "agentes": agentes_raw["agentes"],
        "hooks": resultado["hooks"],
        "primeiro_prompt": resultado["primeiro_prompt"],
    }
