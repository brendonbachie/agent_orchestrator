# agent-orchestrator

Interface web que inicializa projetos Python com CLAUDE.md, subagentes e hooks
gerados automaticamente pelo Claude Code. O usuário descreve o projeto em texto,
revisa e edita a proposta, e o orquestrador cria todos os arquivos e abre o
Claude Code já com o primeiro prompt carregado.

```bash
python app.py        # sobe o servidor em localhost:8000
```

---

## Stack

- **Linguagem:** Python 3.12
- **Backend:** FastAPI + uvicorn
- **Frontend:** HTML + CSS + JavaScript puro (sem framework)
- **Bridge IA:** `claude -p` via subprocess (Claude Code local)
- **Persistência:** `~/.orchestrator/projetos.json` (sem banco de dados)
- **Templates:** `templates/agents/` — biblioteca de agentes reutilizáveis
- **Testes:** pytest + httpx (cliente async pro FastAPI)

---

## Estrutura de Pastas

```
agent-orchestrator/
├── app.py                      # Entry point — sobe FastAPI + serve frontend
├── api/
│   ├── __init__.py
│   ├── agents.py               # GET /agents + POST /agents/{name}/pin — biblioteca e fixados
│   ├── analyze.py              # POST /analyze — análise encadeada em 3 prompts
│   ├── folderpicker.py         # GET /pick-folder — diálogo nativo de pasta
│   ├── generate.py             # POST /generate — escreve arquivos + abre Claude Code
│   └── projects.py             # GET /projects — lista projetos criados
├── core/
│   ├── __init__.py
│   ├── analyzer.py             # Orquestra os 3 prompts encadeados
│   ├── builder.py              # Monta CLAUDE.md, agentes e hooks como strings
│   ├── folderpicker.py         # Lógica do diálogo nativo (tkinter via subprocess)
│   ├── writer.py               # Escreve arquivos + detecta conflitos (check_conflicts)
│   └── launcher.py             # Abre Claude Code com o primeiro prompt
├── templates/
│   ├── agents/                 # Biblioteca de agentes reutilizáveis
│   │   ├── readme-generator.md
│   │   ├── docstring-writer.md
│   │   ├── changelog-builder.md
│   │   ├── test-writer.md
│   │   ├── security-reviewer.md
│   │   └── lambda-reviewer.md
│   └── hooks/                  # Hooks prontos reutilizáveis
│       ├── pre-bash.sh
│       ├── post-write.sh
│       └── stop.sh
├── utils/
│   ├── __init__.py
│   ├── agents_store.py         # Biblioteca global de agentes + fixados (pinned)
│   ├── claude.py               # Wrapper do subprocess `claude -p`
│   └── storage.py              # Lê e escreve projetos.json
├── frontend/
│   ├── index.html              # Tela 1 — descrição do projeto
│   ├── preview.html            # Tela 2 — edição antes de gerar
│   ├── generating.html         # Tela 3 — progresso da geração
│   └── static/
│       ├── style.css
│       └── app.js
└── tests/
    ├── unit/
    │   ├── test_analyzer.py
    │   ├── test_builder.py
    │   └── test_storage.py
    └── integration/
        └── test_api.py

~/.orchestrator/
└── projetos.json               # Histórico de projetos criados
```

---

## Arquitetura e Decisões Importantes

**Bridge via subprocess, não API direta.**
O orquestrador chama `claude -p "prompt"` via subprocess e captura o stdout.
Nunca chamar a API Anthropic diretamente — o objetivo é usar o Claude Code local,
sem API key separada.

**Análise encadeada em 3 prompts.**
O `analyzer.py` roda 3 chamadas sequenciais ao `claude -p`:
1. Analisa stack, padrão de uso e pontos de falha do projeto
2. Sugere agentes (reusando da biblioteca quando possível)
3. Sugere hooks baseado na análise + agentes

Cada prompt recebe o output do anterior como contexto. Nunca tentar resolver
tudo em um prompt único — o resultado é genérico demais.

**Templates primeiro, criação do zero só quando necessário.**
O Prompt 2 recebe a lista de agentes disponíveis em `templates/agents/`.
O Claude decide quais reusar e quais criar do zero. Agentes da biblioteca
são retornados como referência (só o nome). Agentes novos são retornados
com o conteúdo completo.

**Builder só constrói, Writer só escreve.**
`builder.py` monta o conteúdo de cada arquivo como string — sem tocar o disco.
`writer.py` recebe essas strings e escreve os arquivos. Facilita testes e
permite o preview editável antes de gerar.

**Outputs sempre em JSON, validados por schema.**
Todo prompt ao Claude pede resposta em JSON puro — sem markdown, sem explicação.
O `claude.py` faz o parse e lança exceção se não conseguir. O `analyzer.py` ainda
valida cada resposta contra um schema Pydantic (`_Analise`, `_AgentesResult`,
`_Resultado`); chave faltando ou tipo errado vira `ClaudeError` (502) com mensagem
clara, em vez de estourar lá na frente.

**Persistência com escrita atômica.**
`storage.py` grava `projetos.json` via arquivo temporário + `os.replace`, sob um
`threading.Lock` — sem janela de corrupção e sem lost update entre requisições
concorrentes (os endpoints chamam `save_project` via `asyncio.to_thread`).

**Custo de geração contido.**
A geração não pode custar mais tokens do que o projeto economiza. Três medidas:
1. **cwd neutro** — `claude.py` roda o `claude -p` de uma pasta vazia
   (`_neutral_cwd`), senão cada chamada herdaria a pasta do orquestrador e
   carregaria o CLAUDE.md de 8KB dele (medido: ~+4,5k tokens/chamada).
2. **Modelo por etapa** — só a análise (Prompt 1, classificação pura) usa
   `sonnet`; a criação de agentes (Prompt 2) e o artefato final (Prompt 3) usam
   `opus`. Medimos que o Sonnet gera agentes sem frontmatter YAML e em inglês —
   o que quebra a delegação e anula a economia posterior. Ver `run_prompt(model=...)`.
3. **Cache por hash** — `utils/analysis_cache.py` guarda o resultado por
   `hash(descrição + templates)`; gerar a mesma descrição de novo custa zero.

**Dispatcher só vale para projeto grande (gate de complexidade).**
`analyze()` retorna `recomendacao` (`orquestrar` true/false) por heurística do nº de
áreas de especialização. `core/dispatcher.py` executa o `plano` task a task, cada
uma em sessão `claude -p` isolada (`utils.claude.run_task`) no modelo do tier — isso
força o isolamento de contexto que o prompt sozinho não garante. MAS medimos: em
projeto pequeno o dispatcher custa MAIS (3 sessões frias pagam 3× o boot, sem acúmulo
para economizar; calculadora/mini-tarefas ~4× pior). O ganho só aparece em projeto
grande (chamados ~15M tokens). Por isso o frontend só oferece o dispatcher quando
`recomendacao.orquestrar=true`; em projeto simples avisa e pede confirmação. Ganho
sempre-ligado, independente de tamanho = o pin de Sonnet no build.

---

## Fluxo Completo

```
1. POST /analyze  { descricao, pasta }
        ↓
   analyzer.py roda 3 prompts encadeados
        ↓
   Retorna: { claude_md, agentes, hooks, primeiro_prompt }

2. Usuário edita no preview.html

3. POST /generate  { claude_md, agentes, hooks, primeiro_prompt, pasta, sobrescrever }
        ↓
   Se sobrescrever=false e algum arquivo já existe na pasta:
   retorna 409 { detail: { conflitos: [paths] } } — o frontend pede
   confirmação e reenvia com sobrescrever=true
        ↓
   writer.py cria estrutura de pastas e arquivos
   (inclui .claude/primeiro-prompt.txt e .claude/launch.sh)
        ↓
   launcher.py abre o terminal rodando .claude/launch.sh, que faz
   cd no projeto e roda: claude "$(cat .claude/primeiro-prompt.txt)"
   — o prompt nunca passa pela linha de comando do Windows (wt.exe
   trata ';' como separador e quebraria o comando)
```

---

## Os 3 Prompts do Analyzer

### Prompt 1 — Análise do Projeto
```
Analisa esse projeto e retorna APENAS JSON, sem markdown:
{
  "stack": ["linguagem", "frameworks", "ferramentas"],
  "padrao": "cli|api|daemon|web|lambda|biblioteca",
  "pontos_de_falha": ["lista dos riscos principais"],
  "precisa_especializacao": ["áreas que precisam de agente dedicado"]
}

Projeto: {descricao}
```

### Prompt 2 — Sugestão de Agentes
```
Dado essa análise: {analise}
Biblioteca disponível: {lista_templates}

Retorna APENAS JSON, sem markdown:
{
  "agentes": [
    {
      "name": "nome-do-agente",
      "source": "biblioteca|novo",
      "conteudo": "conteúdo completo se novo, null se biblioteca"
    }
  ]
}

Para cada área de especialização identificada:
- Se existe agente similar na biblioteca: source = "biblioteca"
- Se não existe: source = "novo" com conteúdo completo
```

### Prompt 3 — Sugestão de Hooks
```
Projeto: {descricao}
Análise: {analise}
Agentes: {agentes}

Retorna APENAS JSON, sem markdown:
{
  "hooks": [
    {
      "tipo": "PreToolUse|PostToolUse|Stop",
      "matcher": "Bash|Write|null",
      "script": "conteúdo do script bash",
      "motivo": "por que esse hook é necessário"
    }
  ],
  "primeiro_prompt": "primeiro prompt para mandar no Claude Code"
}
```

---

## Convenções de Código

- Todo acesso ao Claude Code passa por `utils/claude.py` — nunca subprocess direto nos módulos
- `api/` só faz parsing de request/response — lógica vai em `core/`
- Outputs do Claude sempre parseados como JSON — nunca processar como texto livre
- Erros do subprocess capturados em `claude.py` e relançados como exceções claras
- Frontend sem frameworks — HTML/CSS/JS puro, sem npm, sem build step

---

## Comandos

```bash
# Setup
pip install -e ".[dev]"

# Rodar
python app.py                    # localhost:8000

# Testes
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest --cov=. tests/

# Lint
ruff check .
mypy .
```

---

## O que NÃO fazer

- Não chamar `subprocess` fora de `utils/claude.py`
- Não chamar a API Anthropic diretamente — sempre via `claude -p`
- Não escrever arquivos no disco fora de `core/writer.py`
- Não colocar lógica nos endpoints de `api/` — vai em `core/`
- Não usar frameworks JavaScript — HTML/CSS/JS puro no frontend
- Não rodar `git commit` ou `git push` no projeto do usuário
- Não sobrescrever arquivos existentes sem confirmar com o usuário
- Não parsear output do Claude com regex — sempre JSON

---

## Fases de Implementação

### Fase 1 — Scaffold
- `pyproject.toml` com dependências
- `app.py` servindo `frontend/index.html` estático
- `utils/claude.py` com wrapper básico do subprocess
- Testar: `python app.py` abre página no browser

### Fase 2 — Análise
- `core/analyzer.py` com os 3 prompts encadeados
- `api/analyze.py` com POST /analyze
- Frontend manda descrição e recebe proposta
- Testar: digita projeto, recebe CLAUDE.md + agentes + hooks em JSON

### Fase 3 — Preview editável
- `frontend/preview.html` com campos editáveis pra cada arquivo
- Usuário pode modificar antes de gerar
- Testar: edita um agente e confirma que a edição é preservada

### Fase 4 — Geração
- `core/builder.py` monta conteúdo dos arquivos
- `core/writer.py` escreve no disco
- `core/launcher.py` abre Claude Code com primeiro prompt
- Testar: clica "Gerar", projeto aparece no disco, Claude Code abre

### Fase 5 — Histórico e qualidade
- `utils/storage.py` + `api/projects.py`
- Lista de projetos criados na interface
- Cobertura de testes > 80%
