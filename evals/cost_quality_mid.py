"""Eval custo+qualidade — ponto INTERMEDIÁRIO (~1.000-1.400 LOC, 7 subsistemas).

Mesmo projeto (controle de gastos) construído de duas formas, AMBAS em sonnet, LIMPO
(sem skills — comparável ao ponto de 200 LOC):
  RAW  — um único `claude` na pasta vazia, spec inteiro (prompt comum).
  ORCH — scaffold hand-authored (CLAUDE.md) + dispatcher task a task (7 tasks).

Objetivo: ver se o ORCH/RAW CAI conforme o projeto cresce (curva dobrando rumo ao
cruzamento). Pontos anteriores: 200 LOC → 2,03× ; 550 LOC → 4,65× (este c/ skills).

Qualidade avaliada DEPOIS (pytest/ruff/LOC). Resultado em evals/_resultado_mid.json
"""

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core import builder, writer  # noqa: E402
from core.dispatcher import ordenar, prompt_da_task  # noqa: E402
from utils.claude import run_task  # noqa: E402

MODEL = "sonnet"

SPEC = (
    "Construa um controle de gastos (expense tracker) em Python, biblioteca pura (só "
    "pytest para teste), SEM CLI. Módulos, cada um em seu arquivo:\n"
    "1. models.py: dataclasses Gasto (id:int, descricao:str, valor:float, categoria:str, "
    "data:str ISO, pago:bool) e Categoria (nome:str, limite_mensal:float|None).\n"
    "2. validacao.py: valida_descricao (não-vazia), valida_valor (>0), valida_categoria "
    "(dentre categorias conhecidas) — cada uma levanta ValueError com mensagem clara.\n"
    "3. storage.py: persistência JSON com ESCRITA ATÔMICA (tempfile + os.replace): "
    "load(path)->dict com gastos e categorias; save(path, gastos, categorias).\n"
    "4. categorias.py: CategoriaService — adicionar(nome, limite), remover(nome), "
    "listar(), definir_limite(nome, limite); nomes únicos.\n"
    "5. servico.py: GastoService — add(descricao, valor, categoria, data), "
    "listar(categoria=None, pago=None, mes=None), marcar_pago(id), atualizar(id, **campos), "
    "remover(id), buscar(texto); ids incrementais; usa validacao.\n"
    "6. relatorios.py: total_geral(gastos), por_categoria(gastos)->dict, "
    "por_mes(gastos)->dict, maiores(gastos, n)->list.\n"
    "7. orcamento.py: checar_orcamento(gastos, categorias, mes)->dict indicando, por "
    "categoria com limite, quanto foi gasto e se estourou.\n"
    "8. tests/: pytest cobrindo models, validacao (erros), storage (round-trip), "
    "categorias, servico (add/listar/marcar_pago/atualizar/remover/buscar), relatorios e orcamento.\n"
    "Type hints, código limpo. Os testes devem passar."
)

CLAUDE_MD = (
    "# Controle de Gastos\n\n"
    "Biblioteca Python pura; só pytest como dependência de teste. Sem CLI.\n\n"
    "## Módulos\n"
    "- `models.py` — dataclasses `Gasto` e `Categoria`\n"
    "- `validacao.py` — validações (levantam `ValueError`)\n"
    "- `storage.py` — persistência JSON com escrita atômica\n"
    "- `categorias.py` — `CategoriaService`\n"
    "- `servico.py` — `GastoService` (regras de negócio, ids incrementais)\n"
    "- `relatorios.py` — agregações\n"
    "- `orcamento.py` — checagem de limite por categoria\n"
    "- `tests/` — pytest por módulo\n\n"
    "## Convenções\n"
    "- Type hints em tudo; funções pequenas.\n"
    "- `storage.save` usa escrita atômica (tempfile + `os.replace`).\n"
    "- Validações levantam `ValueError` com mensagem clara.\n"
)

PLANO = [
    {"ordem": 1,
     "task": "Implemente models.py (dataclasses Gasto e Categoria) e validacao.py "
     "(valida_descricao, valida_valor, valida_categoria).",
     "contrato": "models.Gasto(id,descricao,valor,categoria,data,pago); "
     "models.Categoria(nome,limite_mensal); validacao.valida_* levantam ValueError.",
     "agente": None, "modelo": MODEL, "depende_de": []},
    {"ordem": 2,
     "task": "Implemente storage.py: load(path)->dict e save(path, gastos, categorias) "
     "com escrita atômica (tempfile + os.replace).",
     "contrato": "storage.load(path)->dict; storage.save(path, gastos, categorias)->None.",
     "agente": None, "modelo": MODEL, "depende_de": [1]},
    {"ordem": 3,
     "task": "Implemente categorias.py: CategoriaService com adicionar, remover, listar, "
     "definir_limite; nomes únicos.",
     "contrato": "categorias.CategoriaService() com adicionar(nome,limite), remover(nome), "
     "listar(), definir_limite(nome,limite).",
     "agente": None, "modelo": MODEL, "depende_de": [1]},
    {"ordem": 4,
     "task": "Implemente servico.py: GastoService com add, listar, marcar_pago, atualizar, "
     "remover, buscar; ids incrementais; usa validacao.",
     "contrato": "servico.GastoService() com add(descricao,valor,categoria,data), "
     "listar(categoria,pago,mes), marcar_pago(id), atualizar(id,**campos), remover(id), buscar(texto).",
     "agente": None, "modelo": MODEL, "depende_de": [1]},
    {"ordem": 5,
     "task": "Implemente relatorios.py: total_geral, por_categoria, por_mes, maiores.",
     "contrato": "relatorios.total_geral(gastos), por_categoria(gastos)->dict, "
     "por_mes(gastos)->dict, maiores(gastos,n)->list.",
     "agente": None, "modelo": MODEL, "depende_de": [1]},
    {"ordem": 6,
     "task": "Implemente orcamento.py: checar_orcamento(gastos, categorias, mes)->dict com "
     "gasto e estouro por categoria com limite.",
     "contrato": "orcamento.checar_orcamento(gastos, categorias, mes)->dict.",
     "agente": None, "modelo": MODEL, "depende_de": [1, 3]},
    {"ordem": 7,
     "task": "Escreva tests/ com pytest cobrindo models, validacao (erros), storage "
     "(round-trip), categorias, servico, relatorios e orcamento.",
     "contrato": "tests/ passam no pytest.",
     "agente": None, "modelo": MODEL, "depende_de": [1, 2, 3, 4, 5, 6]},
]


def _tokens(usage: dict) -> dict:
    return {
        "input": usage.get("input_tokens", 0),
        "cache_creation": usage.get("cache_creation_input_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "output": usage.get("output_tokens", 0),
    }


def _somar(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in {"input", "cache_creation", "cache_read", "output"}}


def run_raw(pasta: str) -> tuple[dict, float, dict]:
    print("\n── RAW (prompt único, pasta vazia) ──", flush=True)
    ini = time.monotonic()
    try:
        r = run_task(SPEC, MODEL, pasta, timeout=3000)
    except Exception as e:  # noqa: BLE001
        print(f"  ERRO: {e}", flush=True)
        return {}, 0.0, {"erro": str(e)}
    dt = time.monotonic() - ini
    print(f"  ok={r['ok']} turns={r.get('num_turns')} {dt:.0f}s cost=${r.get('cost_usd')}", flush=True)
    return _tokens(r.get("usage") or {}), float(r.get("cost_usd") or 0), {
        "ok": r.get("ok"), "turns": r.get("num_turns"), "segundos": round(dt)}


def run_orch(pasta: str) -> tuple[dict, float, dict]:
    print("\n── ORCH (CLAUDE.md + dispatcher, 7 tasks, sem skills) ──", flush=True)
    files = builder.build(CLAUDE_MD, [], [], None, PLANO)
    writer.write(files, pasta)
    print(f"  scaffold: {len(files)} arquivos", flush=True)
    tokens: dict = {}
    custo = 0.0
    feitas: list[dict] = []
    detalhe = []
    for task in ordenar(PLANO):
        ini = time.monotonic()
        try:
            r = run_task(prompt_da_task(task, feitas), MODEL, pasta, timeout=1800)
        except Exception as e:  # noqa: BLE001
            print(f"  task {task.get('ordem')}: ERRO {e}", flush=True)
            detalhe.append({"ordem": task.get("ordem"), "erro": str(e)})
            feitas.append(task)
            continue
        dt = time.monotonic() - ini
        print(f"  task {task.get('ordem')} ({task.get('task','')[:40]}): ok={r['ok']} "
              f"turns={r.get('num_turns')} {dt:.0f}s cost=${r.get('cost_usd')}", flush=True)
        tokens = _somar(tokens, _tokens(r.get("usage") or {}))
        custo += float(r.get("cost_usd") or 0)
        detalhe.append({"ordem": task.get("ordem"), "ok": r.get("ok"),
                        "turns": r.get("num_turns"), "segundos": round(dt)})
        feitas.append(task)
    return tokens, custo, {"n_tasks": len(PLANO), "tasks": detalhe}


def main() -> None:
    raw_dir = tempfile.mkdtemp(prefix="qMID-raw-")
    orch_dir = tempfile.mkdtemp(prefix="qMID-orch-")
    print(f"raw_dir  = {raw_dir}\norch_dir = {orch_dir}", flush=True)

    rt, rc, rmeta = run_raw(raw_dir)
    ot, oc, ometa = run_orch(orch_dir)

    cols = ["input", "cache_creation", "cache_read", "output"]
    print(f"\n{'='*64}\nCUSTO (build, modelo {MODEL})\n{'='*64}", flush=True)
    print(f"{'':18}{'RAW':>16}{'ORCH':>16}", flush=True)
    for c in cols:
        print(f"{c:18}{rt.get(c, 0):>16,}{ot.get(c, 0):>16,}", flush=True)
    tr, to = sum(rt.values()), sum(ot.values())
    print(f"{'TOTAL tokens':18}{tr:>16,}{to:>16,}", flush=True)
    print(f"{'custo USD':18}{rc:>16.4f}{oc:>16.4f}", flush=True)
    if tr and rc:
        print(f"\n  ORCH/RAW  →  tokens {to/tr:.2f}x   ·   custo {oc/rc:.2f}x", flush=True)

    resultado = {
        "raw_dir": raw_dir, "orch_dir": orch_dir,
        "raw": {"tokens": rt, "custo": rc, "meta": rmeta},
        "orch": {"tokens": ot, "custo": oc, "meta": ometa},
    }
    out = Path(__file__).parent / "_resultado_mid.json"
    out.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultado salvo em {out}\nAvalie a qualidade nas duas pastas acima.", flush=True)


if __name__ == "__main__":
    main()
