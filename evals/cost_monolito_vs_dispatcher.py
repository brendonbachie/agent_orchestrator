"""Eval de CUSTO — monólito (prompt comum) vs orquestrador (dispatcher).

Constrói o MESMO projetinho de duas formas e mede os tokens reais (envelope
`--output-format json` do claude):

  RAW  — um único `claude` numa pasta vazia, spec inteiro (prompt comum no terminal).
  ORCH — CLAUDE.md + dispatcher task a task, cada uma em sessão isolada.

Ambos via `utils.claude.run_task` (mesmo modelo, mesmo `acceptEdits`) → apples-to-apples;
a ÚNICA diferença é monólito vs split (+ a presença do CLAUDE.md no ORCH, como na vida real).
Plano hand-authored para controlar custo/variância — NÃO inclui o custo de geração do
analyzer (3 prompts), que no mundo real entraria como custo fixo extra do ORCH.

Rodar:  python evals/cost_monolito_vs_dispatcher.py
ATENÇÃO: faz builds reais (escreve arquivos em pastas temp). Gasta tokens de verdade.
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.dispatcher import ordenar, prompt_da_task  # noqa: E402
from utils.claude import run_task  # noqa: E402

MODEL = "sonnet"

SPEC = (
    "Crie uma calculadora em Python. Arquivo calc.py com funções soma(a,b), "
    "subtrai(a,b), multiplica(a,b) e divide(a,b) — divide deve levantar ValueError "
    "se b for 0. Arquivo test_calc.py com testes pytest cobrindo as 4 funções e o "
    "ValueError. Os testes devem passar."
)

CLAUDE_MD = (
    "# Calculadora\n\n"
    "Biblioteca Python pura (só pytest como dependência de teste).\n\n"
    "## Convenções\n"
    "- Funções em `calc.py`; testes em `test_calc.py` (pytest).\n"
    "- `divide(a, 0)` levanta `ValueError`.\n"
)

PLANO = [
    {
        "ordem": 1,
        "task": "Implemente calc.py com soma, subtrai, multiplica e divide. "
        "divide(a, b) levanta ValueError se b == 0.",
        "contrato": "calc.py expõe soma(a,b), subtrai(a,b), multiplica(a,b), divide(a,b).",
        "agente": None,
        "modelo": MODEL,
        "depende_de": [],
    },
    {
        "ordem": 2,
        "task": "Crie test_calc.py com pytest cobrindo as 4 funções e o ValueError de divide.",
        "contrato": "test_calc.py cobre calc.py e passa no pytest.",
        "agente": None,
        "modelo": MODEL,
        "depende_de": [1],
    },
]


def _tokens(usage: dict) -> dict:
    """Normaliza os campos de token do envelope do claude."""
    return {
        "input": usage.get("input_tokens", 0),
        "cache_creation": usage.get("cache_creation_input_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "output": usage.get("output_tokens", 0),
    }


def _somar(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}


def run_raw(pasta: str) -> tuple[dict, float]:
    print("\n── RAW (prompt único, pasta vazia, sem CLAUDE.md) ──")
    ini = time.monotonic()
    r = run_task(SPEC, MODEL, pasta)
    print(f"  ok={r['ok']} turns={r.get('num_turns')} {time.monotonic()-ini:.0f}s "
          f"cost=${r.get('cost_usd')}")
    print(f"  usage={r.get('usage')}")
    return _tokens(r.get("usage") or {}), float(r.get("cost_usd") or 0)


def run_orch(pasta: str) -> tuple[dict, float]:
    print("\n── ORCH (CLAUDE.md + dispatcher, task a task isolada) ──")
    Path(pasta, "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    tokens: dict = {}
    custo = 0.0
    feitas: list[dict] = []
    for task in ordenar(PLANO):
        ini = time.monotonic()
        r = run_task(prompt_da_task(task, feitas), MODEL, pasta)
        print(f"  task {task['ordem']}: ok={r['ok']} turns={r.get('num_turns')} "
              f"{time.monotonic()-ini:.0f}s cost=${r.get('cost_usd')}")
        print(f"    usage={r.get('usage')}")
        tokens = _somar(tokens, _tokens(r.get("usage") or {}))
        custo += float(r.get("cost_usd") or 0)
        feitas.append(task)
    return tokens, custo


def main() -> None:
    raw_dir = tempfile.mkdtemp(prefix="cmp-raw-")
    orch_dir = tempfile.mkdtemp(prefix="cmp-orch-")
    print(f"raw_dir = {raw_dir}\norch_dir = {orch_dir}")

    rt, rc = run_raw(raw_dir)
    ot, oc = run_orch(orch_dir)

    cols = ["input", "cache_creation", "cache_read", "output"]
    print(f"\n{'='*64}\nCOMPARAÇÃO DE CUSTO (modelo {MODEL})\n{'='*64}")
    print(f"{'':18}{'RAW':>16}{'ORCH':>16}")
    for c in cols:
        print(f"{c:18}{rt.get(c, 0):>16,}{ot.get(c, 0):>16,}")
    tr, to = sum(rt.values()), sum(ot.values())
    print(f"{'TOTAL tokens':18}{tr:>16,}{to:>16,}")
    print(f"{'custo USD':18}{rc:>16.4f}{oc:>16.4f}")
    if tr and rc:
        print(f"\n  ORCH/RAW  →  tokens {to/tr:.2f}x   ·   custo {oc/rc:.2f}x")
    print("\nNota: custo de geração do analyzer (3 prompts opus) NÃO incluído — "
          "no mundo real soma como custo fixo extra do ORCH.")


if __name__ == "__main__":
    main()
