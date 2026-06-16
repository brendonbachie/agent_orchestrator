import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from core.builder import DISCIPLINA_TESTES
from utils.analysis_cache import cache_get, cache_key, cache_set
from utils.claude import ClaudeError, run_prompt

_T = TypeVar("_T", bound=BaseModel)

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
}}

Regras para agentes novos (source="novo"):
- O "conteudo" DEVE começar com frontmatter YAML, exatamente neste formato:
  ---
  name: <igual ao campo name>
  description: <quando acionar — comece com "Use proativamente quando ...">
  ---
  É a "description" que faz o Claude Code delegar ao agente; sem ela, o agente
  nunca é acionado.
- Escreva todo o conteúdo no MESMO idioma da descrição do projeto.
- Após o frontmatter, descreva responsabilidades e diretrizes técnicas específicas."""

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
  "claude_md": "CLAUDE.md completo: visão geral, stack, estrutura, convenções e comandos",
  "plano": [
    {{
      "ordem": 1,
      "task": "o que construir nesta task",
      "contrato": "interface/schema/saída que as tasks dependentes vão usar",
      "agente": "nome-do-agente responsável ou null (para cola/integração)",
      "modelo": "free|sonnet|opus",
      "depende_de": []
    }}
  ]
}}

Regras para os hooks:
- Hooks que protegem dados sensíveis devem referenciar o arquivo de persistência
  REAL do projeto (deduza da stack/análise — ex.: o arquivo .db do SQLite ou o
  .json usado), nunca um nome genérico que não existe no projeto.

Regras para o claude_md:
- DEVE incluir uma seção "## Agentes" listando cada agente planejado, no formato
  "delegue ao agente <nome> (abrindo um subagente via Task) para <quando usar>".
  Deixe explícito que o trabalho ESPECIALIZADO deve rodar em SUBAGENTE (ferramenta
  Task), não inline na thread principal — isso mantém o contexto principal enxuto
  e barato (a releitura do contexto é o que mais custa).
- Mencione os hooks configurados e o que eles bloqueiam/verificam.
- Seja CONCISO: o CLAUDE.md é relido a CADA turno, então o tamanho dele custa em
  toda interação. Prefira bullets curtos a prosa; foque em convenções, fronteiras
  e o que NÃO fazer — sem tutorial, sem repetir o óbvio.
- Inclua uma seção de disciplina de testes com EXATAMENTE este texto: {disciplina}

Regras para o primeiro_prompt:
- Deve instruir EXPLICITAMENTE o uso da ferramenta Task para cada subsistema
  especializado: "Abra um subagente com o agente <nome> para <tarefa>", em vez de
  só "use o agente <nome>". Mencionar não basta — é a instrução imperativa de abrir
  subagente que faz a delegação realmente acontecer.
- Reserve o trabalho leve de cola/integração para a thread principal (inline); só
  o trabalho pesado e especializado vai para subagentes.
- Construa em FASES por subsistema: implemente um, rode seus testes, e só então
  avance. Mantenha UMA sessão contínua — NÃO use /clear nem reinicie o contexto.
  O isolamento do contexto pesado deve vir dos SUBAGENTES (cada um roda em contexto
  próprio e descartável e devolve só um resumo), mantendo a thread principal enxuta
  SEM fragmentar a sessão. Medimos: fragmentar com /clear quebra a delegação e
  encarece; uma sessão única delegando aos subagentes é mais barata e mais coerente.
- Peça que os testes de cada subsistema rodem antes de integrar o próximo.
- Deve mandar SEGUIR o "plano" (em .claude/plano-build.md), task a task, na ordem.

Regras para o plano:
- Decomponha o build em tasks. Cada task traz: o que construir, um CONTRATO
  (interface/schema/saída que as tasks dependentes consomem), o agente responsável
  (ou null para cola/integração) e o tier de modelo.
- Tier de modelo: "free" = mecânico/boilerplate/docstrings; "sonnet" = implementação
  padrão; "opus" = arquitetura, modelo de dados, segurança e decisões críticas.
- Ordene como um DAG: fundação (modelo de dados, contratos) primeiro em opus; folhas
  paralelas depois em tier mais barato. Use "depende_de" com as ordens das tasks-base."""


# ── Schemas das respostas do Claude ──────────────────────────────────────────
# Cada prompt é validado contra um schema. Chaves faltando ou tipos errados viram
# ClaudeError (502) com mensagem clara, em vez de KeyError (500) lá na frente.
# extra="ignore" tolera campos a mais que o Claude eventualmente inventa.


class _Analise(BaseModel):
    model_config = ConfigDict(extra="ignore")
    stack: list[str] = []
    padrao: str = ""
    pontos_de_falha: list[str] = []
    precisa_especializacao: list[str] = []


class _Agente(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""
    source: str = "novo"
    conteudo: str | None = None


class _AgentesResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    agentes: list[_Agente] = []


class _Hook(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tipo: str
    matcher: str | None = None
    script: str = ""
    motivo: str = ""


class _TaskPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ordem: int = 0
    task: str = ""
    contrato: str = ""
    agente: str | None = None
    modelo: str = "sonnet"
    depende_de: list[int] = []


class _Resultado(BaseModel):
    model_config = ConfigDict(extra="ignore")
    claude_md: str
    hooks: list[_Hook] = []
    primeiro_prompt: str = ""
    plano: list[_TaskPlan] = []


def _validar(model: type[_T], data: object, etapa: str) -> _T:
    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise ClaudeError(
            f"resposta do Claude na etapa '{etapa}' fora do schema esperado: {e}"
        ) from e


def _list_templates() -> list[str]:
    return sorted(p.stem for p in _TEMPLATES_DIR.glob("*.md"))


def _agentes_resumidos(agentes: list[_Agente]) -> list[dict[str, str]]:
    """Versão enxuta dos agentes para o Prompt 3 — nome, origem e um resumo.

    Evita reenviar o markdown completo dos agentes novos (que o Prompt 3 não
    precisa) e mantém contexto suficiente para a seção ## Agentes e o primeiro
    prompt citarem cada agente corretamente.
    """
    resumidos: list[dict[str, str]] = []
    for a in agentes:
        resumo = ""
        if a.conteudo:
            for linha in a.conteudo.splitlines():
                s = linha.strip()
                if s and not s.startswith(("#", "---", "name:", "description:")):
                    resumo = s[:200]
                    break
        resumidos.append({"name": a.name, "source": a.source, "resumo": resumo})
    return resumidos


def _recomendacao(analise: _Analise) -> dict[str, object]:
    """Heurística determinística: vale a pena orquestrar este projeto?

    Orquestração compensa em projetos com várias áreas especializadas (trabalho
    pesado e isolável). Em projeto simples ela custa MAIS (medido: calculadora
    3,7x). Decidido sem nenhuma chamada extra ao Claude.
    """
    n = len(analise.precisa_especializacao)
    if n >= 2:
        return {
            "orquestrar": True,
            "motivo": f"{n} áreas especializadas identificadas — a orquestração "
            "(agentes + isolamento de contexto) tende a compensar.",
        }
    return {
        "orquestrar": False,
        "motivo": "Projeto com pouca especialização. Provavelmente sai mais barato "
        "com um prompt único direto no Claude Code — medimos a orquestração custar "
        "mais que o prompt comum em projetos simples.",
    }


def analyze(descricao: str) -> dict[str, object]:
    templates = _list_templates()

    # Mesma descrição + biblioteca → reusa o resultado, sem gastar tokens de novo.
    chave = cache_key(descricao, templates)
    em_cache = cache_get(chave)
    if em_cache is not None:
        return em_cache

    # Sonnet só na análise (Prompt 1), que é classificação pura e barata.
    # A criação de agentes (Prompt 2) e o artefato final (Prompt 3) usam Opus:
    # medimos que o Sonnet gera agentes sem frontmatter e em inglês — o que
    # quebra a delegação e, com ela, toda a economia de token posterior.
    analise = _validar(
        _Analise,
        run_prompt(_PROMPT_1.format(descricao=descricao), timeout=180, model="sonnet"),
        "análise",
    )

    agentes = _validar(
        _AgentesResult,
        run_prompt(
            _PROMPT_2.format(
                analise=json.dumps(analise.model_dump(), ensure_ascii=False),
                lista_templates=json.dumps(templates, ensure_ascii=False),
            ),
            timeout=180,
            model="opus",
        ),
        "agentes",
    )

    resultado = _validar(
        _Resultado,
        run_prompt(
            _PROMPT_3.format(
                descricao=descricao,
                analise=json.dumps(analise.model_dump(), ensure_ascii=False),
                agentes=json.dumps(_agentes_resumidos(agentes.agentes), ensure_ascii=False),
            ),
            timeout=180,
            model="opus",
        ),
        "resultado",
    )

    saida: dict[str, object] = {
        "claude_md": resultado.claude_md,
        "agentes": [a.model_dump() for a in agentes.agentes],
        "hooks": [h.model_dump() for h in resultado.hooks],
        "primeiro_prompt": resultado.primeiro_prompt,
        "plano": [t.model_dump() for t in resultado.plano],
        "recomendacao": _recomendacao(analise),
    }
    cache_set(chave, saida)
    return saida
