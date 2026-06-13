# Agent Orchestrator

> Interface web que prepara projetos para serem desenvolvidos com o Claude Code —
> gerando `CLAUDE.md`, subagentes, hooks e um plano de build a partir de uma
> descrição em texto. **Foco: projetos melhores gastando menos tokens.**

Em vez de abrir o Claude Code num diretório vazio e explicar tudo do zero, você
descreve o projeto, revisa a proposta e o orquestrador monta todo o ambiente —
opcionalmente **executando o build task a task** em contexto isolado.

O que distingue este projeto não é gerar arquivos: é que **cada decisão de custo foi
medida, não suposta** — inclusive as que contrariaram a intuição (orquestrar nem
sempre compensa). Veja a seção [O que medimos](#-o-que-medimos).

---

## O problema

Preparar um bom ambiente de desenvolvimento assistido por IA é trabalhoso: escrever um
`CLAUDE.md` com as convenções, definir subagentes especializados, configurar hooks de
automação e dar um primeiro prompt que oriente o trabalho. Tudo manual, e repetido a
cada projeto.

## A ideia

```
descrever  →  analisar (3 prompts)  →  revisar/editar  →  gerar  →  abrir/executar
```

O orquestrador roda uma análise encadeada, propõe o andaime completo, deixa você
editar e então escreve os arquivos no disco — abrindo o Claude Code já configurado ou
executando o plano automaticamente.

---

## ✨ Recursos

- **Análise encadeada em 3 prompts** — diagnostica stack/padrão/riscos, sugere
  agentes (reusando uma biblioteca quando possível) e gera `CLAUDE.md` + hooks +
  primeiro prompt + plano de tasks.
- **Preview editável** — revise e ajuste tudo antes de gerar.
- **Gate de complexidade** — recomenda *não* orquestrar quando o projeto é simples
  demais para compensar.
- **Dispatcher** — executa o plano task a task, cada uma em **sessão isolada** e no
  **modelo do seu tier** (Sonnet/Opus), com progresso ao vivo (streaming) e gate de
  testes entre as tasks.
- **Medidor de custo** — lê o transcript real da sessão e mostra o consumo de tokens
  e o **custo em USD** por modelo.
- **Biblioteca de agentes e hooks** reutilizáveis, com agentes "fixados" que entram em
  todo projeto novo.
- **Proteções** — confirmação antes de sobrescrever, sanitização de nomes (path
  traversal), escrita atômica do histórico, validação de schema das respostas da IA.

---

## Como funciona

```
TELA 1  index.html ──POST /analyze──▶ analyzer (Sonnet → Opus → Opus)
                                         │  CLAUDE.md, agentes, hooks,
                                         │  primeiro_prompt, plano, recomendação
TELA 2  preview.html  (revisar/editar) ─┘
                       └──POST /generate──▶ builder monta + writer grava no disco
TELA 3  generating.html
        ├─ launcher: abre o Claude Code interativo com o primeiro prompt
        └─ POST /dispatch: executa o plano task a task (streaming, contexto isolado)
```

**Dois caminhos de execução:** abrir o Claude interativo (você acompanha) ou rodar o
dispatcher (automático, recomendado para projetos grandes — veja o porquê abaixo).

---

## Começando

### Requisitos
- **Python 3.12** (no Windows)
- **Claude Code** instalado no **WSL** (o orquestrador o chama via `wsl.exe`)

### Instalar e rodar
```bash
pip install -e ".[dev]"
python app.py            # http://localhost:8000
```

### Qualidade
```bash
python -m pytest tests/ -q     # 132 testes (rápidos; todas as chamadas à IA são mockadas)
python -m ruff check .         # lint
python -m mypy core/ utils/    # tipagem
```

---

## Arquitetura

```
api/        camada HTTP fina — só parsing de request/response
core/       lógica de negócio (analyzer, builder, writer, dispatcher, usage, ...)
utils/      ferramentas (claude, storage, cache, sessões, verify)
templates/  biblioteca de agentes e hooks reutilizáveis
frontend/   HTML/CSS/JS puro, sem framework
tests/      unit (cada módulo) + integration (a API)
```

**Regra de ouro:** `api/` não tem lógica — chama `core/`. Todo acesso ao Claude passa
por `utils/claude.py`. O `builder` **monta** os arquivos como strings e o `writer`
**grava** — separação que mantém tudo testável e permite o preview.

---

## 📊 O que medimos

A engenharia de fundo do projeto. Tudo abaixo veio de medição real, não de suposição:

- **~94% do custo é releitura de contexto (`cache_read`)** — o gasto cresce porque o
  modelo relê a janela inteira a cada turno. Atacar isso é o que economiza.
- **Composição de custo (build grande):** `cache_read` 14,3M ≫ `cache_creation` 658k >
  `output` 251k > `input_fresco` 50k (o menor).
- **Orquestrar só compensa em projeto grande.** Em projeto pequeno, a orquestração
  custou **3,7×–4× mais** (o overhead de sessões frias supera a economia). Daí o gate
  de complexidade.
- **Pedir delegação no prompt não basta** — o modelo raramente abre subagentes
  sozinho. Por isso o dispatcher **força** o isolamento de contexto, executando cada
  task em sua própria sessão.
- **Ganho garantido, independente de tamanho:** rodar o build em Sonnet em vez de Opus
  (~5× mais barato por token).

---

## Roadmap

- Acumular **métricas reais de uso** (tokens/custo por build) para calibrar o gate por
  dados, em vez de heurística.
- **Tiering com modelos gratuitos** para o trabalho mecânico, reservando o Claude para
  o crítico.
- **Abort** no dispatcher (interromper um build que azedou).
- Robustez do parser de JSON e do medidor de consumo.

---

## Documentação

- **`GUIA.md`** — super guia técnico: cada termo, cada função, e o *porquê* de cada
  decisão (ideal para aprender e ensinar o projeto).
- **`Agent Orchestrator - Projeto.pdf`** — guia + análise de engenharia em PDF.
- **`CLAUDE.md`** — manual de convenções do próprio orquestrador.
