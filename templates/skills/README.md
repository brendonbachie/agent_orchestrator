# Biblioteca de Skills

Skills reutilizáveis — irmã de `templates/agents/` e `templates/hooks/`. Cada skill
segue o layout nativo do Claude Code: uma pasta `<nome>/SKILL.md` (mais arquivos de
apoio na mesma pasta, quando a skill os referencia).

Diferente de um agente (trabalho pesado isolado que o modelo *delega*) e de um hook
(script determinístico disparado por evento), uma **skill** é um *procedimento* que o
modelo carrega **sob demanda**: só o `name` + `description` ficam no contexto até a
skill ser acionada, então o corpo entra. Por isso o critério de curadoria abaixo é
estrito — skill boa é **procedimento concreto**, não conselho vago nem despejo de doc.

---

## O que está aqui (e por quê)

| Skill | Por que entrou |
|---|---|
| **systematic-debugging** | Procedimento de causa-raiz em 4 fases, framework-agnóstico — roda em qualquer projeto/SO. Inclui 3 arquivos de apoio (`root-cause-tracing`, `defense-in-depth`, `condition-based-waiting`). |
| **verification-before-completion** | O mais alinhado com a tese do projeto: *verifique o efeito (rode o comando), não a decisão*. É a versão-skill do gate de testes (`utils/verify.py`). |
| **using-git-worktrees** | Isolamento de contexto no nível de filesystem — irmão conceitual do `core/dispatcher.py`. Funciona no WSL (git/bash). |

## O que ficou de fora (decisão consciente)

- **test-driven-development** — redundante com o que o projeto já força via `templates/hooks/stop.sh` (roda pytest) + agente `test-writer`.
- **finishing-a-development-branch** — conflita com a regra do projeto "não rodar `git commit`/`push` no projeto do usuário" (ver `CLAUDE.md`).
- **Skills de pesquisa/produtividade** (tapestry, youtube, epub/pdf, invoices, etc.) — categoria errada: são ferramentas de trabalho-de-conhecimento pessoal, não procedimentos de projeto de software.
- **llm-council** — skill legítima, mas antitética à tese de custo (≈11 chamadas de modelo por invocação) e não é skill de dev. Pertence ao workspace pessoal, não à biblioteca gerada.

---

## Procedência

As três skills foram puxadas de **[obra/superpowers](https://github.com/obra/superpowers)**
(© 2025 Jesse Vincent), licença **MIT**. Conteúdo mantido praticamente verbatim para
preservar a fidelidade; a curadoria (o que entra/sai) é nossa.

Notas de adaptação ainda pendentes (intencionalmente não alteradas para não divergir da
origem):

- `using-git-worktrees` referencia um caminho legado do superpowers
  (`~/.config/superpowers/worktrees/`); inofensivo (é só fallback), mas trocável por um
  caminho neutro numa versão project-native.
- `systematic-debugging` cita dois arquivos opcionais de exemplo (`find-polluter.sh`,
  `condition-based-waiting-example.ts`) que **não** foram puxados — são ilustrações
  TS/bash, irrelevantes para um projeto Python. As referências são "soft" (não quebram a skill).

---

## Estado: integrada ao fluxo

A biblioteca está **ligada** às três camadas:

1. **Seleção** — `core/analyzer.py` (`_list_skills`) passa nome + description de cada
   skill ao Prompt 2, que devolve `skills: [...]` (só nomes da biblioteca; nomes
   inventados ou inexistentes são filtrados — não criamos skills novas).
2. **Escrita** — `core/builder.py` (`_skill_files`) copia a pasta inteira da skill
   selecionada para `.claude/skills/<nome>/` (SKILL.md + apoios); `core/writer.py`
   grava com `newline="\n"`. `_normalize_name` + exigência de um SKILL.md real barram
   path traversal e nome desconhecido. O endpoint `POST /generate` repassa `skills`.
3. **Forçar no dispatcher** — `core/dispatcher.py` (`prompt_da_task`) injeta as skills
   instaladas no prompt de cada task, mandando ler o SKILL.md correspondente em vez de
   depender do auto-trigger por description. O endpoint `POST /dispatch` repassa `skills`.

O frontend carrega `skills` da análise até `/generate` e `/dispatch` (`preview.js`,
`generating.js`).

Também dá para uso manual: copiar uma pasta de skill para o `.claude/skills/` de
qualquer projeto.
