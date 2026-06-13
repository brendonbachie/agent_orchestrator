"""Eval de SELEÇÃO de skills — mede se o Prompt 2 escolhe as skills certas.

As skills curadas (systematic-debugging, verification-before-completion,
using-git-worktrees) são higiene de dev transversal: aplicam-se a quase todo
projeto de software. Então não medimos casamento de domínio — medimos dois modos
de falha:

  - SUB-SELEÇÃO: num projeto de dev real, deixou de pegar as óbvias? (recall)
  - SOBRE-SELEÇÃO: num pedido trivial/não-dev, selecionou à toa? (false positive)

O `gold` (expected) é JULGAMENTO do autor, não verdade absoluta — para skills
transversais o "certo" é fuzzy de propósito; o valor está em flagrar os extremos.

Rodar:  python evals/skill_selection.py
Cada caso chama `analyze()` de verdade (3 chamadas claude). Resultado fica em cache
por descrição — para re-medir variância, limpe ~/.orchestrator/cache.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analyzer import analyze  # noqa: E402

# tipo: "dev" = projeto de software (espera selecionar as relevantes)
#       "trivial" = pedido trivial/não-dev (espera selecionar NADA)
CASOS: list[dict] = [
    {
        "id": "dev-grande-multimodulo",
        "tipo": "dev",
        "descricao": "Microsserviço em FastAPI com autenticação JWT, banco PostgreSQL, "
        "módulos separados (auth, usuários, pagamentos) e testes de integração. "
        "Já apresenta bugs intermitentes em produção.",
        "expected": {"systematic-debugging", "verification-before-completion", "using-git-worktrees"},
    },
    {
        "id": "dev-refatoracao-legada",
        "tipo": "dev",
        "descricao": "Refatorar uma base legada em Python com falhas intermitentes "
        "difíceis de reproduzir, mantendo a suíte de testes passando.",
        "expected": {"systematic-debugging", "verification-before-completion"},
    },
    {
        "id": "dev-api-media",
        "tipo": "dev",
        "descricao": "API REST em Flask com CRUD de produtos, validação de entrada e "
        "testes automatizados com pytest.",
        "expected": {"verification-before-completion"},
    },
    {
        "id": "dev-cli-pequeno",
        "tipo": "dev",
        "descricao": "CLI em Python que converte um arquivo CSV para JSON, com alguns "
        "testes unitários.",
        "expected": {"verification-before-completion"},
    },
    {
        "id": "trivial-script",
        "tipo": "trivial",
        "descricao": "Um script de 15 linhas que renomeia arquivos numa pasta "
        "adicionando a data no nome.",
        "expected": set(),
    },
    {
        "id": "nao-dev-poema",
        "tipo": "trivial",
        "descricao": "Escreva um poema sobre o outono.",
        "expected": set(),
    },
]


def rodar() -> None:
    soma_hits = soma_expected = 0
    sobre_selecao = 0  # casos trivial/não-dev que selecionaram algo
    casos_trivial = 0
    t0 = time.monotonic()

    print(f"\n{'='*78}\nEVAL — Seleção de skills ({len(CASOS)} casos)\n{'='*78}\n")

    for caso in CASOS:
        ini = time.monotonic()
        try:
            resultado = analyze(caso["descricao"])
        except Exception as e:  # noqa: BLE001 — eval não pode morrer num caso
            print(f"✗ {caso['id']}: ERRO — {e}\n")
            continue
        dt = time.monotonic() - ini

        selected = set(resultado.get("skills") or [])
        expected = caso["expected"]
        hits = selected & expected
        missed = expected - selected
        extra = selected - expected

        if caso["tipo"] == "dev":
            soma_hits += len(hits)
            soma_expected += len(expected)
        else:
            casos_trivial += 1
            if selected:
                sobre_selecao += 1

        marca = "✓" if (not missed and not (caso["tipo"] == "trivial" and selected)) else "✗"
        print(f"{marca} [{caso['tipo']}] {caso['id']}  ({dt:.0f}s)")
        print(f"    selecionou: {sorted(selected) or '—'}")
        print(f"    esperado:   {sorted(expected) or '—'}")
        if missed:
            print(f"    SUB-SELEÇÃO (faltou): {sorted(missed)}")
        if extra:
            rotulo = "SOBRE-SELEÇÃO" if caso["tipo"] == "trivial" else "extra (aceitável p/ transversal)"
            print(f"    {rotulo}: {sorted(extra)}")
        print()

    recall = (soma_hits / soma_expected) if soma_expected else float("nan")
    print(f"{'='*78}\nRESUMO  (tempo total: {time.monotonic() - t0:.0f}s)\n{'='*78}")
    print(f"  Recall em casos dev:        {soma_hits}/{soma_expected}  = {recall:.0%}")
    print(f"  Sobre-seleção (trivial):    {sobre_selecao}/{casos_trivial} casos selecionaram algo indevido")
    print()


if __name__ == "__main__":
    rodar()
