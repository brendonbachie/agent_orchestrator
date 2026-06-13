"""Eval de CUSTO + QUALIDADE num projeto de ~1k LOC (o ponto de cruzamento).

Constrói o MESMO projeto de duas formas e mede tokens reais:
  RAW  — um único `claude` na pasta vazia, spec inteiro (prompt comum no terminal).
  ORCH — analyze() real → escreve scaffold (CLAUDE.md+skills+agentes) → dispatcher
         task a task (cada uma sessão isolada).

Ambos em `sonnet` para isolar a variável "monólito vs split" (model-tiering é outra
alavanca). O custo de GERAÇÃO do analyzer (3 prompts opus) NÃO é capturado aqui
(`run_prompt` não expõe tokens) — só o build (dispatch) é medido com precisão.

A QUALIDADE é avaliada DEPOIS, fora deste script (pytest/ruff/LOC/leitura), porque o
build em acceptEdits não roda Bash.

Rodar:  python evals/cost_quality_1k.py     (faz builds reais; gasta tokens)
Resultado durável em evals/_resultado_1k.json
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
from core.analyzer import analyze  # noqa: E402
from core.dispatcher import ordenar, prompt_da_task  # noqa: E402
from utils.claude import run_task  # noqa: E402

MODEL = "sonnet"

SPEC = (
    "Construa um gerenciador de tarefas (todo) por linha de comando em Python, sem "
    "dependências além de pytest. Subsistemas, cada um em seu arquivo:\n"
    "1. models.py: dataclass Task com id (int), titulo (str), feito (bool), "
    "prioridade ('baixa'|'media'|'alta'), tags (list[str]) e criado_em (str ISO).\n"
    "2. storage.py: salvar/carregar a lista de tarefas em JSON com ESCRITA ATÔMICA "
    "(arquivo temporário + os.replace). Funções load(path)->list[Task] e save(path, tasks).\n"
    "3. validacao.py: validar titulo não-vazio e prioridade dentre as permitidas; "
    "levantar ValueError com mensagem clara.\n"
    "4. servico.py: classe TaskService com add(titulo, prioridade, tags), "
    "listar(filtro_feito=None, tag=None), concluir(id), remover(id) e buscar(texto). "
    "Ids incrementais.\n"
    "5. stats.py: resumo(tasks)->dict com contagem por status, por prioridade e total.\n"
    "6. cli.py: argparse com comandos add, list, done, rm, stats; lê/grava via storage "
    "num arquivo tasks.json.\n"
    "7. tests/: pytest cobrindo models, storage (round-trip), validacao (casos de erro), "
    "servico (add/concluir/remover/buscar) e stats.\n"
    "Código limpo, com type hints. Os testes devem passar."
)


def _tokens(usage: dict) -> dict:
    return {
        "input": usage.get("input_tokens", 0),
        "cache_creation": usage.get("cache_creation_input_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "output": usage.get("output_tokens", 0),
    }


def _somar(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in {"input", "cache_creation", "cache_read", "output"}}


def _analyze_retry(descricao: str, tentativas: int = 3, backoff: float = 30.0) -> dict:
    for i in range(tentativas):
        try:
            return analyze(descricao)
        except Exception as e:  # noqa: BLE001
            print(f"  analyze falhou ({e}); retry {i+1}/{tentativas}", flush=True)
            if i == tentativas - 1:
                raise
            time.sleep(backoff)
    raise RuntimeError("inalcançável")


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
        "ok": r.get("ok"), "turns": r.get("num_turns"), "segundos": round(dt)
    }


def run_orch(pasta: str) -> tuple[dict, float, dict]:
    print("\n── ORCH: analyze() real ──", flush=True)
    res = _analyze_retry(SPEC)
    plano = res.get("plano") or []
    skills = res.get("skills") or []
    print(f"  plano: {len(plano)} tasks · skills: {skills} · "
          f"agentes: {[a.get('name') for a in res.get('agentes') or []]}", flush=True)
    print(f"  recomendacao.orquestrar = {res.get('recomendacao', {}).get('orquestrar')}", flush=True)

    files = builder.build(
        res["claude_md"], res.get("agentes") or [], res.get("hooks") or [],
        res.get("primeiro_prompt"), plano, skills,
    )
    writer.write(files, pasta)
    print(f"  scaffold escrito: {len(files)} arquivos", flush=True)

    print("\n── ORCH: dispatcher task a task ──", flush=True)
    tokens: dict = {}
    custo = 0.0
    feitas: list[dict] = []
    detalhe = []
    for task in ordenar(plano):
        ini = time.monotonic()
        try:
            r = run_task(prompt_da_task(task, feitas, skills), MODEL, pasta, timeout=1800)
        except Exception as e:  # noqa: BLE001 — uma task ruim não derruba o resto
            print(f"  task {task.get('ordem')}: ERRO {e}", flush=True)
            detalhe.append({"ordem": task.get("ordem"), "erro": str(e)})
            feitas.append(task)
            continue
        dt = time.monotonic() - ini
        print(f"  task {task.get('ordem')} ({task.get('task','')[:45]}): "
              f"ok={r['ok']} turns={r.get('num_turns')} {dt:.0f}s cost=${r.get('cost_usd')}", flush=True)
        tokens = _somar(tokens, _tokens(r.get("usage") or {}))
        custo += float(r.get("cost_usd") or 0)
        detalhe.append({"ordem": task.get("ordem"), "ok": r.get("ok"),
                        "turns": r.get("num_turns"), "segundos": round(dt)})
        feitas.append(task)

    return tokens, custo, {"n_tasks": len(plano), "skills": skills, "tasks": detalhe}


def main() -> None:
    raw_dir = tempfile.mkdtemp(prefix="q1k-raw-")
    orch_dir = tempfile.mkdtemp(prefix="q1k-orch-")
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
    out = Path(__file__).parent / "_resultado_1k.json"
    out.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultado salvo em {out}", flush=True)
    print("Avalie a QUALIDADE rodando pytest/ruff/LOC nas duas pastas acima.", flush=True)


if __name__ == "__main__":
    main()
