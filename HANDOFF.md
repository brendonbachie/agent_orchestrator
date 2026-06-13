# Handoff — Agent Orchestrator (primer de contexto)

Cole/abra isto numa nova sessão para continuar o trabalho sem o histórico anterior.

## O que é o projeto
Interface web (FastAPI) que prepara um ambiente Claude Code a partir de uma descrição:
gera `CLAUDE.md` + subagentes + hooks + primeiro-prompt + plano de tasks, deixa revisar,
escreve no disco e abre/executa. **Meta: projetos melhores gastando menos tokens.**

- Pasta: `C:\Users\brend\OneDrive\Área de Trabalho\Projetos\agent_orchestrator`
- Guia completo do código: **`GUIA.md`** (leia primeiro — explica cada função e o porquê).
- Análise crítica recente: **`ANALISE.md`**.

## Ambiente (importante)
- Orquestrador roda no **Python do Windows**; o `claude` roda no **WSL** (usuário brendon).
  `utils/claude.py` chama `wsl.exe claude`. Nunca use `-u root`.
- Rodar: `python app.py` → http://localhost:8000
- Testes/lint: `python -m pytest tests/ -q` (132 testes, ~1s, tudo mockado) ·
  `python -m ruff check .` (limpo) · `python -m mypy core/ utils/` (alguns `dict` crus
  pré-existentes, não-bloqueantes).

## Arquitetura
- `api/` — camada HTTP fina (sem lógica). `core/` — lógica. `utils/` — ferramentas
  (claude, storage, cache, sessões, verify). `templates/` — agentes e hooks prontos.
  `frontend/` — HTML/CSS/JS puro.
- Regra de ouro: `api/` só faz parsing; lógica em `core/`; todo acesso ao Claude em
  `utils/claude.py`. `builder` monta, `writer` grava (separação testável).

## Fluxo
descrever (`POST /analyze`, 3 prompts encadeados) → revisar (`/preview`) →
gerar (`POST /generate`) → abrir Claude interativo (`launcher`) **ou** executar o plano
(`POST /dispatch`, streaming, task a task isolada).

## Estado atual — TUDO implementado e testado (132 testes)
1. Sonnet no build (~5×) · 3. isolamento por fase no prompt · 4. CLAUDE.md enxuto ·
5. gate de complexidade (`recomendacao.orquestrar`) · 6. medidor de tokens com custo
USD (`core/usage.py` + `GET /usage`) · 7. retry no `run_prompt` · 8. hook com arquivo
de dados real · 9. autodetecção do Python · 10. plano de tasks DAG · 11. dispatcher
(`core/dispatcher.py` + `run_task` + `POST /dispatch`) · gate de testes
(`utils/verify.py`) · streaming NDJSON no dispatcher · gate ligado ao dispatcher no
frontend. Também: proteção contra sobrescrita (409), sanitização de path traversal,
parser JSON robusto, escrita atômica no storage, validação Pydantic, cwd neutro, cache
por hash.

## Descobertas-chave (medidas)
- **~94% do custo é `cache_read`** (releitura de contexto acumulado). O inimigo é o
  contexto inchando, não "ler caro". Não há truque de compressão: cache já é o desconto.
- **Ordem de custo (build do chamados):** cache_read 14,3M ≫ cache_creation 658k >
  output 251k > input_fresco 50k (o menor).
- **Orquestrar só compensa em projeto grande.** Calculadora ~200 LOC: orquestrador
  **3,7× pior**. mini-tarefas (dispatcher): **4× pior**. Chamados ~4.000 LOC / 15,2M
  tokens / ~$55 em Opus: aí o monólito explode e o isolamento venceria.
- **Pedir delegação no prompt não basta** (1 subagente em 52 turnos). Por isso o
  dispatcher executa a divisão à força.
- **Lever sempre-ligado e garantido = Sonnet no build (~5×)**; o resto é condicional
  ao tamanho (por isso o gate).

## Limitação atual conhecida
No dispatcher (`acceptEdits`), as tasks **escrevem arquivos mas não rodam Bash** —
o gate de testes roda pelo orquestrador (Python chama `pytest`), não dentro do build.

## Roadmap (pendências, em ordem de valor)
1. **Acumular métricas reais** (registrar projeto + tokens + custo + orquestrado?) para
   o gate aprender por dados, não heurística. (Maior valor; vira hipótese em evidência.)
2. **#12 — tier free (OpenCode)** para tasks mecânicas, Claude no crítico.
3. **Robustez:** `_extract_json` tolerar prosa com chaves antes do JSON; casar sessão
   por `cwd` dentro do `.jsonl` (não pelo nome do diretório).
4. **Abort no dispatcher** (parar build ruim → economiza tokens).
5. (Futuro) abstração de driver de execução (WSL/Linux nativo); SQLite se virar multiusuário.

## Memória persistente do projeto
`~/.claude/.../memory/`: `agent-orchestrator-objetivo-economia.md` (objetivo + achados +
levers) e `agent-orchestrator-test-env.md` (ambiente: Python do Windows, claude no WSL
como brendon).
