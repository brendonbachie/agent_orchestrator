# Handoff Atual — Agent Orchestrator (investigação de custo + mudanças)

> Primer pra continuar em nova janela, do zero de contexto. Leia junto com `GUIA.md`
> (código função a função) e `ANALISE.md` (a tese). Este doc cobre o que **esta
> investigação descobriu e mudou** — é mais atual que o `HANDOFF.md` antigo.

---

## TL;DR — o que importa

1. **A promessa "projetos melhores gastando menos tokens" NÃO vale** no caminho padrão
   (dispatcher) nem em projeto pequeno. Medido à exaustão (200, 550, 650 LOC →
   orquestrar custa 2–4,65× MAIS, qualidade empatada).
2. **Existe UMA config que paga**, descoberta nos testes: **sessão interativa única +
   `--model opus` + agentes na `.claude/` + primeiro-prompt imperativo de delegação**.
   Aí o modelo lê o DAG, abre subagentes (delegação dispara), o supervisor fica enxuto.
3. **Otimização nova, implementada e PROVADA: tier de modelo por subagente.** Cada
   agente roda no seu preço (mecânico→sonnet, crítico→opus) via `model:` no frontmatter.
   Medido headless: **~37% mais barato** num build pequeno, mais em build grande.
4. **O valor real do orquestrador é gerar o scaffold** (CLAUDE.md + agentes + plano +
   primeiro-prompt) — barato (~$2,5) e bom. **Não** é o dispatcher (esse perde sempre).

---

## Ambiente & comandos

- Orquestrador roda no **Python do Windows**; o `claude` roda no **WSL** (usuário
  brendon) via `wsl.exe claude`. Nunca `-u root`.
- Subir: `python app.py` → http://localhost:8000
- Testes: `python -m pytest tests/ -q` (**142 testes**) · `python -m ruff check .`
- Usuário no **Claude Pro** (cota de ~5h compartilhada entre o claude do WSL e esta
  sessão — throttle observado em rajadas de opus).

---

## O que mudou no código nesta sessão

1. **Hardening de segurança em `utils/claude.py` — MANTIDO (bom).**
   Prompt por stdin (não por argv → mata argument-injection), separador implícito,
   allowlist de modelo (`_safe_model`: free→sonnet, só sonnet/opus/haiku), validação de
   `cwd` no `run_task`. +6 testes em `tests/unit/test_claude.py`.

2. **Skills — TENTADO e REVERTIDO (líquido zero).**
   Cheguei a integrar uma biblioteca `templates/skills/` (de obra/superpowers) com
   seleção no Prompt 2, escrita no `.claude/skills/` e injeção forçada no dispatcher.
   Medido: forçar skill em toda task fria inflou custo e gerou cruft (no modo
   acceptEdits sem Bash). **Tudo revertido.** Não reintroduzir sem necessidade.

3. **`/clear` removido do primeiro-prompt gerado (`core/analyzer.py`, `_PROMPT_3`).**
   A regra antiga mandava "fase por subsistema com /clear / contexto fresco" — isso
   FRAGMENTA a sessão e mata a delegação (medido: build fragmentado deu 1 subagente vs
   monólito interativo que deu 4–5). Agora o prompt manda **"UMA sessão contínua, NÃO
   use /clear, o isolamento vem dos SUBAGENTES"**.

4. **Tier de modelo no frontmatter dos agentes (`core/builder.py`) — NOVO, a otimização.**
   `build()` mapeia `task.agente → task.modelo` do plano e injeta `model: <tier>` no
   frontmatter de cada agente (`_inject_agent_model`, `_tier_para_model`: free→haiku,
   sonnet→sonnet, opus→opus). Assim, na config vencedora (supervisor opus), cada
   subagente roda no seu preço. +4 testes em `test_builder.py`.

---

## A investigação — números medidos (o coração)

### Projeto pequeno: orquestrar PERDE
| LOC | metodologia | ORCH/RAW custo |
|---|---|---|
| 200 (calculadora) | limpo | **2,03×** (orquestrar pior) |
| 550 (task manager) | com skills (inflado) | 4,65× |
| 650 (controle gastos) | limpo | **2,29×** |

Os pontos limpos (200, 650) ficam **planos em ~2×** — a curva NÃO dobra rumo ao
cruzamento. O monólito fica eficiente (~250k tokens, ~20 turns) até ~650 LOC; **não
balloona**. Cruzamento real está bem além (multi-k LOC, fora do alcance do Pro).

### 3 arquiteturas no mesmo projeto (~650 LOC)
`monólito puro $0,53` < `dispatcher frio $1,21` < `sessão+subagentes $1,31`.
O dispatcher (N sessões `claude -p` frias) paga N boots → perde. Subagentes-em-sessão
a essa escala: o supervisor acumula + paga subagentes = pior de tudo.

### O chamados (projeto grande real, ~4.000 LOC)
15,2M tokens / ~$55 / opus / 23h / **8 subagentes** (delegação FUNCIONOU). Importante:
o `cost3.py` do usuário reportava "0 subagentes" — era **bug de parsing** (conta
sidechain errado). A verdade está no `grep -o '"subagent_type":"[^"]*"'`.

### A config vencedora (RAG2 / RAG3, projeto grande delegável)
- Sessão **interativa opus** + agentes + prompt imperativo → o modelo abre os
  subagentes (4–5) e o supervisor fica enxuto.
- **opus delega; sonnet faz inline.** Então a SESSÃO deve ser opus pra delegar (o
  velho lever "sempre sonnet ~5×" se inverte em projeto grande delegável).

### A otimização (tier por subagente) — PROVADA com número
Build headless, supervisor opus, 3 validadores (2 agentes sonnet + 1 opus):
| modelo | trabalho | custo |
|---|---|--:|
| sonnet | os 2 subagentes mecânicos | **$0,200** |
| opus | supervisor + subagente crítico | $0,487 |
| **total tiered** | | **$0,688** |
Tudo-opus seria ~$1,10 → **~37% mais barato**, e a economia escala com quanto trabalho
cai pros subagentes baratos.

---

## Limitações de medição (LEIA — pra não repetir erros que cometi)

- **Transcript INTERATIVO é cego aos subagentes** (`sidechain=0`): só mede a thread
  principal (supervisor). Os meus "$9,25 do RAG2" eram **supervisor-only** (subestimado).
  Pra medir o custo dos subagentes: build **headless** `claude -p --output-format json`
  → o `modelUsage` lista cada modelo + custo (incl. subagentes).
- **Variância de build é ENORME**: mesmo spec → RAG2 2.486 LOC vs RAG3 6.537 LOC (2,6×).
  Metade do RAG3 eram testes exaustivos (subagente focado escreve testes de 700 linhas).
  Um A/B de n=1 não conclui nada.
- **Geração é barata** (~$2,5 / ~120k tokens, P1 sonnet + P2/P3 opus) — troco perto de
  um build grande. O scaffold é o valor; o custo de gerá-lo é desprezível.

---

## Reutilização de agentes (decisão)

Dois tipos: **papel** (test-writer, security-reviewer, docstring — domínio-agnóstico,
REUTILIZÁVEIS) vs **domínio** (ingestao-naval, grounding-rag — específicos,
DESCARTÁVEIS, gerados frescos). Biblioteca só faz sentido pros de papel — e enxuta,
**com `model:` pré-setado** (test-writer→sonnet, security-reviewer→opus) e pinada. Não
investir em catálogo grande (geração é barata, modelo especializa bem na hora).

---

## Pendências / próximos passos (em ordem de valor)

CONCLUÍDAS em 2026-06-21:
- ✅ **`launch.sh` por gate**: `_launch_script(orquestrar)` em `core/builder.py` sobe em
  `opus` quando `recomendacao.orquestrar=true`, `sonnet` caso contrário. O `orquestrar`
  flui frontend (`preview.js`) → `POST /generate` (`api/generate.py`) → `build()`.
- ✅ **Diretriz anti over-testing**: `DISCIPLINA_TESTES` em `core/builder.py`, injetada no
  CLAUDE.md (`_ensure_testing_discipline`), no primeiro-prompt (`_com_disciplina_testes`)
  e no Prompt 3 do analyzer (`{disciplina}`). 149 testes verdes.
- ✅ **Memória do projeto**: criada `agent-orchestrator-config-vencedora-delegacao.md`
  (delegação FUNCIONA + config vencedora + tier por subagente provado) e cruzada na
  `dispatcher-custo-medido`.

Abertas:
1. **Resume**: o `claude -c` / `claude --resume` já resolve "rodar de onde parou" no
   launcher (nativo; já há `.claude/resume.sh`). Faltaria checkpoint no dispatcher (se for
   manter o dispatcher — mas ele perde, considerar aposentar).
2. **Calibrar o gate por dados**: registrar projeto + tokens + custo + orquestrado? para o
   gate aprender o limiar por dados, não heurística.

---

## Arquivos temporários criados (pode limpar)

- Em `C:\Users\brend\`: `measure_rag2.py`, `measure_gen.py`, `measure_rag3.py`,
  `diag_rag3.py`, `loc_rag3.sh`, `run_rag2_tests.sh`, `run_rag3_tests.sh`,
  `probe_model.sh`, `probe_model2.sh`, `test_tiers.sh`.
- Em `evals/`: `_force_gen.py`, `_write_scaffold.py` (+ os `cost_*.py` / `eval_*.py` /
  `_resultado_*.json` da investigação — esses valem como registro reprodutível).
- Pastas de teste: `Área de Trabalho/RAG2`, `RAG3` (builds), `/tmp/test-tiers`,
  `/tmp/probe-model*` (no WSL).

---

## Veredito da investigação (1 parágrafo)

O orquestrador não cumpre "menos tokens" no jeito padrão nem em projeto pequeno — aí o
monólito puro ganha. Mas, em **projeto grande delegável**, rodado **interativo + opus +
com o scaffold gerado**, a delegação dispara e o supervisor fica enxuto; e **com o tier
de modelo por subagente** (implementado e provado, ~37%+) você junta delegação
confiável com economia. O valor do projeto é **gerar esse scaffold bom e barato** — não
o dispatcher. Tudo foi medido, e várias intuições (inclusive minhas) caíram no caminho.
