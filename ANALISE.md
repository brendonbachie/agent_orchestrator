# Análise de Engenharia

### Avaliação técnica do Agent Orchestrator: o que o torna sólido e a tese por trás dele

> Esta análise parte do código real e dos números medidos durante o
> desenvolvimento. O foco aqui é o que sustenta o projeto e a engenharia de fundo —
> as forças e a tese central.

---

## 1. As forças do projeto

**Engenharia guiada por medição.** O traço que mais distingue este projeto é não
assumir — medir. A maioria dos sistemas de agentes parte da premissa de que "mais
agentes e mais autonomia = melhor". Aqui, cada decisão de custo foi testada antes de
virar regra, inclusive as que contrariaram a intuição inicial. Isso eleva o projeto
de "ferramenta" para "investigação de engenharia".

**Separação `builder` monta / `writer` grava.** O builder produz um dicionário
`{caminho: conteúdo}` sem tocar o disco; o writer só persiste. Essa fronteira deixa
toda a montagem testável sem I/O e permite o preview editável. É a melhor decisão
arquitetural do projeto e aparece refletida na suíte de testes.

**`_neutral_cwd` — contra o vazamento de contexto.** Rodar a análise a partir de uma
pasta vazia impede que o Claude leia o `CLAUDE.md` do próprio orquestrador e se
confunda. Parece detalhe, mas economiza ~4,5k tokens por chamada e elimina uma classe
silenciosa de erro (o modelo seguindo regras que não são do projeto-alvo).

**Modelo por tier (Sonnet na triagem, Opus na geração).** Decisão correta e
fundamentada: a triagem (classificação) é barata e o Sonnet dá conta; a geração de
agentes exige o Opus porque o Sonnet falha no frontmatter YAML — e frontmatter quebrado
inutiliza o mecanismo de delegação. Não é economia cega; é economia onde não custa
qualidade.

**Dispatcher + ordenação topológica (DAG).** Planos longos saturam o contexto: no 5º
passo o modelo esquece as restrições do 1º. Quebrar o plano em sessões frias, na ordem
de dependências, faz cada parte rodar com foco total e histórico limpo. É o
componente determinístico que tira a opacidade do comportamento do modelo.

---

## 2. A descoberta central (a tese do projeto)

Três fatos medidos sustentam todo o design:

1. **~94% do custo é releitura de contexto (`cache_read`).** O inimigo não é "ler
   caro" — é reler a mesma coisa a cada turno, numa janela que só cresce. Não existe
   truque de compressão: o cache já é o desconto máximo (~0,1× do input). Só dá para
   **carregar menos** (isolamento) ou **trocar a taxa** (modelo mais barato).

2. **A composição de custo importa.** Pelos números reais de um build grande:
   `cache_read` (14,3M) ≫ `cache_creation` (658k) > `output` (251k) >
   **`input_fresco` (50k — o menor)**. Quem quer cortar custo deve mirar a curva de
   releitura e o preço por token (output/cache), não o input fresco.

3. **Orquestrar é investimento que só se paga em projeto grande.** Medido: em projeto
   pequeno a orquestração custa **3,7×–4× mais** (o boot de 3 sessões frias supera
   qualquer economia, porque não há contexto acumulado para isolar). Num projeto de
   ~4.000 LOC e build de 15,2M tokens, o monólito explode em `cache_read` e o
   isolamento venceria.

E um achado desconfortável, mas honesto: **pedir delegação no prompt não funciona de
forma confiável.** Mesmo instruindo "abra um subagente", o modelo delegou ~1 vez em
52 turnos — ele tem viés de persistência (prefere insistir na mesma sessão a abrir mão
do controle). Por isso o isolamento precisa ser **forçado** pelo dispatcher, não
sugerido.

---

## 3. Veredito

No estado atual, o Agent Orchestrator é melhor descrito como uma **plataforma de
experimentação para otimização de custo e contexto em desenvolvimento assistido por
IA** do que como um simples gerador de ambientes. A maturidade não está no volume de
features, e sim na disciplina de **medir cada hipótese** — inclusive aceitando quando
a medição contraria a intenção (orquestrar nem sempre vale). É essa postura, mais do
que qualquer componente isolado, que separa o projeto de uma ferramenta comum.
