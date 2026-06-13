"""Eval custo+qualidade — versão ENXUTA (Opção A): sonnet-only, sem opus.

Mesmo projeto (gerenciador de tarefas, ~500-600 LOC, 5 módulos + testes) construído
de duas formas, AMBAS em sonnet:
  RAW  — um único `claude` na pasta vazia, spec inteiro (prompt comum).
  ORCH — scaffold hand-authored (CLAUDE.md + 2 skills) + dispatcher task a task.

Sem `analyze()` → zero chamadas opus (que eram o throttle-risk e parte do custo).
Plano hand-authored para controlar custo/variância — transparente. Reusa o builder e
o dispatcher REAIS; só a geração do plano é substituída.

Qualidade avaliada DEPOIS (pytest/ruff/LOC/leitura). Resultado em evals/_resultado_A.json
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
SKILLS = ["systematic-debugging", "verification-before-completion"]

SPEC = (
    "Construa um gerenciador de tarefas (todo) em Python, biblioteca pura (só pytest "
    "para teste), SEM CLI. Módulos, cada um em seu arquivo:\n"
    "1. models.py: dataclass Task com id:int, titulo:str, feito:bool, "
    "prioridade:'baixa'|'media'|'alta', tags:list[str], criado_em:str (ISO).\n"
    "2. validacao.py: valida_titulo (não-vazio) e valida_prioridade (dentre as "
    "permitidas), levantando ValueError com mensagem clara.\n"
    "3. storage.py: load(path)->list[Task] e save(path, tasks) com ESCRITA ATÔMICA "
    "(tempfile + os.replace).\n"
    "4. servico.py: TaskService com add(titulo, prioridade, tags), "
    "listar(filtro_feito=None, tag=None), concluir(id), remover(id) e buscar(texto); "
    "ids incrementais; usa validacao.\n"
    "5. stats.py: resumo(tasks)->dict com total, por_status e por_prioridade.\n"
    "6. tests/: pytest cobrindo models, validacao (casos de erro), storage (round-trip), "
    "servico e stats.\n"
    "Type hints, código limpo. Os testes devem passar."
)

CLAUDE_MD = (
    "# Gerenciador de Tarefas (todo)\n\n"
    "Biblioteca Python pura; só pytest como dependência de teste. Sem CLI nesta versão.\n\n"
    "## Módulos\n"
    "- `models.py` — dataclass `Task`\n"
    "- `validacao.py` — validações (levantam `ValueError`)\n"
    "- `storage.py` — persistência JSON com escrita atômica\n"
    "- `servico.py` — `TaskService` (regras de negócio, ids incrementais)\n"
    "- `stats.py` — resumo agregado\n"
    "- `tests/` — pytest por módulo\n\n"
    "## Convenções\n"
    "- Type hints em tudo; funções pequenas.\n"
    "- `storage.save` usa escrita atômica (tempfile + `os.replace`).\n"
    "- Erros de validação levantam `ValueError` com mensagem clara.\n"
)

PLANO = [
    {
        "ordem": 1,
        "task": "Implemente models.py (dataclass Task) e validacao.py.",
        "contrato": "models.Task(id:int, titulo:str, feito:bool, prioridade:str, "
        "tags:list[str], criado_em:str). validacao.valida_titulo(t) e "
        "validacao.valida_prioridade(p) levantam ValueError.",
        "agente": None, "modelo": MODEL, "depende_de": [],
    },
    {
        "ordem": 2,
        "task": "Implemente storage.py: load(path)->list[Task] e save(path, tasks) com "
        "escrita atômica (tempfile + os.replace).",
        "contrato": "storage.load(path)->list[Task]; storage.save(path, tasks)->None.",
        "agente": None, "modelo": MODEL, "depende_de": [1],
    },
    {
        "ordem": 3,
        "task": "Implemente servico.py: TaskService com add, listar, concluir, remover, "
        "buscar; ids incrementais; usa validacao.",
        "contrato": "servico.TaskService() com add(titulo,prioridade,tags), "
        "listar(filtro_feito,tag), concluir(id), remover(id), buscar(texto).",
        "agente": None, "modelo": MODEL, "depende_de": [1],
    },
    {
        "ordem": 4,
        "task": "Implemente stats.py: resumo(tasks)->dict com total, por_status e por_prioridade.",
        "contrato": "stats.resumo(tasks)->dict.",
        "agente": None, "modelo": MODEL, "depende_de": [1],
    },
    {
        "ordem": 5,
        "task": "Escreva tests/ com pytest cobrindo models, validacao (erros), storage "
        "(round-trip), servico (add/concluir/remover/buscar) e stats.",
        "contrato": "tests/ passam no pytest.",
        "agente": None, "modelo": MODEL, "depende_de": [1, 2, 3, 4],
    },
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
        r = run_task(SPEC, MODEL, pasta, timeout=2400)
    except Exception as e:  # noqa: BLE001
        print(f"  ERRO: {e}", flush=True)
        return {}, 0.0, {"erro": str(e)}
    dt = time.monotonic() - ini
    print(f"  ok={r['ok']} turns={r.get('num_turns')} {dt:.0f}s cost=${r.get('cost_usd')}", flush=True)
    return _tokens(r.get("usage") or {}), float(r.get("cost_usd") or 0), {
        "ok": r.get("ok"), "turns": r.get("num_turns"), "segundos": round(dt)
    }


def run_orch(pasta: str) -> tuple[dict, float, dict]:
    print("\n── ORCH: scaffold + dispatcher (sonnet) ──", flush=True)
    files = builder.build(CLAUDE_MD, [], [], None, PLANO, SKILLS)
    writer.write(files, pasta)
    print(f"  scaffold: {len(files)} arquivos · skills: {SKILLS}", flush=True)

    tokens: dict = {}
    custo = 0.0
    feitas: list[dict] = []
    detalhe = []
    for task in ordenar(PLANO):
        ini = time.monotonic()
        try:
            r = run_task(prompt_da_task(task, feitas, SKILLS), MODEL, pasta, timeout=1800)
        except Exception as e:  # noqa: BLE001
            print(f"  task {task.get('ordem')}: ERRO {e}", flush=True)
            detalhe.append({"ordem": task.get("ordem"), "erro": str(e)})
            feitas.append(task)
            continue
        dt = time.monotonic() - ini
        print(f"  task {task.get('ordem')} ({task.get('task','')[:42]}): ok={r['ok']} "
              f"turns={r.get('num_turns')} {dt:.0f}s cost=${r.get('cost_usd')}", flush=True)
        tokens = _somar(tokens, _tokens(r.get("usage") or {}))
        custo += float(r.get("cost_usd") or 0)
        detalhe.append({"ordem": task.get("ordem"), "ok": r.get("ok"),
                        "turns": r.get("num_turns"), "segundos": round(dt)})
        feitas.append(task)
    return tokens, custo, {"n_tasks": len(PLANO), "skills": SKILLS, "tasks": detalhe}


def main() -> None:
    raw_dir = tempfile.mkdtemp(prefix="qA-raw-")
    orch_dir = tempfile.mkdtemp(prefix="qA-orch-")
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
    out = Path(__file__).parent / "_resultado_A.json"
    out.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultado salvo em {out}\nAvalie a qualidade nas duas pastas acima.", flush=True)


if __name__ == "__main__":
    main()
