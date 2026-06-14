"""Arquitetura C — sessão ÚNICA com subagentes (vs monólito e dispatcher).

Roda UMA sessão `claude -p` cujo primeiro-prompt é um ORQUESTRADOR: enumera os
subsistemas (a mesma DAG do dispatcher) e manda abrir um SUBAGENTE (ferramenta Task)
para cada, em paralelo onde não há dependência. Um boot só + isolamento via subagente
+ paralelo — a "terceira via" que o usuário viu no projeto de chamados.

Mesmo projeto (controle de gastos ~650 LOC) e mesmo CLAUDE.md do eval intermediário,
então compara direto com A (monólito) e B (dispatcher) salvos em _resultado_mid.json.

IMPORTANTE: com subagentes, o `total_cost_usd` do envelope agrega a sessão inteira
(inclui subagentes); já o breakdown de `usage` pode refletir só a thread principal —
por isso a COMPARAÇÃO PRINCIPAL é por custo USD.

Rodar:  python evals/cost_arch_subagents.py   (1 build real; gasta tokens)
"""

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.dispatcher import ordenar  # noqa: E402
from utils.claude import run_task  # noqa: E402

MODEL = "sonnet"

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
    {"ordem": 1, "task": "models.py (dataclasses Gasto e Categoria) e validacao.py "
     "(valida_descricao, valida_valor, valida_categoria).",
     "contrato": "models.Gasto(id,descricao,valor,categoria,data,pago); "
     "models.Categoria(nome,limite_mensal); validacao.valida_* levantam ValueError.",
     "depende_de": []},
    {"ordem": 2, "task": "storage.py: load(path)->dict e save(path, gastos, categorias) "
     "com escrita atômica (tempfile + os.replace).",
     "contrato": "storage.load(path)->dict; storage.save(path, gastos, categorias)->None.",
     "depende_de": [1]},
    {"ordem": 3, "task": "categorias.py: CategoriaService com adicionar, remover, listar, "
     "definir_limite; nomes únicos.",
     "contrato": "categorias.CategoriaService() com adicionar/remover/listar/definir_limite.",
     "depende_de": [1]},
    {"ordem": 4, "task": "servico.py: GastoService com add, listar, marcar_pago, atualizar, "
     "remover, buscar; ids incrementais; usa validacao.",
     "contrato": "servico.GastoService() com add/listar/marcar_pago/atualizar/remover/buscar.",
     "depende_de": [1]},
    {"ordem": 5, "task": "relatorios.py: total_geral, por_categoria, por_mes, maiores.",
     "contrato": "relatorios.total_geral/por_categoria/por_mes/maiores.",
     "depende_de": [1]},
    {"ordem": 6, "task": "orcamento.py: checar_orcamento(gastos, categorias, mes)->dict.",
     "contrato": "orcamento.checar_orcamento(gastos, categorias, mes)->dict.",
     "depende_de": [1, 3]},
    {"ordem": 7, "task": "tests/ com pytest cobrindo models, validacao (erros), storage "
     "(round-trip), categorias, servico, relatorios e orcamento.",
     "contrato": "tests/ passam no pytest.",
     "depende_de": [1, 2, 3, 4, 5, 6]},
]


def supervisor_prompt(plano: list[dict]) -> str:
    linhas = [
        "Você é o ORQUESTRADOR deste build. NÃO implemente os módulos na thread principal.",
        "Para CADA subsistema abaixo, use a ferramenta Task para abrir um SUBAGENTE "
        "dedicado que implementa SOMENTE aquele módulo seguindo o contrato, em contexto "
        "próprio.",
        "Subsistemas SEM dependência entre si DEVEM ser abertos EM PARALELO (várias "
        "chamadas Task na MESMA resposta). Respeite a ordem de dependências.",
        "Leia o CLAUDE.md do projeto antes de começar.",
        "",
        "Subsistemas:",
    ]
    for t in ordenar(plano):
        deps = t.get("depende_de") or []
        dep_txt = f" (depende de: {', '.join(map(str, deps))})" if deps else " (sem dependências)"
        linhas.append(f"{t['ordem']}. {t['task']}{dep_txt}")
        if t.get("contrato"):
            linhas.append(f"   contrato: {t['contrato']}")
    linhas += [
        "",
        "Estratégia: abra a fundação (1) primeiro; quando pronta, abra as folhas "
        "independentes (2,3,4,5,6) EM PARALELO numa só resposta; por fim os testes (7). "
        "Ao final, confirme que tudo se integra.",
    ]
    return "\n".join(linhas)


def _tokens(usage: dict) -> dict:
    return {
        "input": usage.get("input_tokens", 0),
        "cache_creation": usage.get("cache_creation_input_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "output": usage.get("output_tokens", 0),
    }


def main() -> None:
    pasta = tempfile.mkdtemp(prefix="qC-subag-")
    Path(pasta, "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    print(f"dir = {pasta}", flush=True)

    print("\n── C: sessão única + subagentes ──", flush=True)
    ini = time.monotonic()
    prompt = supervisor_prompt(PLANO)
    r = None
    for i in range(4):  # absorve throttle transitório (stderr vazio, exit 1)
        try:
            r = run_task(prompt, MODEL, pasta, timeout=3000)
            break
        except Exception as e:  # noqa: BLE001
            print(f"  tentativa {i+1} falhou ({e}); backoff 45s", flush=True)
            if i == 3:
                raise
            time.sleep(45)
    assert r is not None
    dt = time.monotonic() - ini
    tok = _tokens(r.get("usage") or {})
    custo_c = float(r.get("cost_usd") or 0)
    print(f"  ok={r['ok']} turns={r.get('num_turns')} {dt:.0f}s cost=${custo_c}", flush=True)
    print(f"  usage(thread principal)={r.get('usage')}", flush=True)

    # A e B do eval intermediário (mesmo projeto), para comparação direta.
    mid = json.loads((Path(__file__).parent / "_resultado_mid.json").read_text(encoding="utf-8"))
    custo_a = mid["raw"]["custo"]
    custo_b = mid["orch"]["custo"]

    print(f"\n{'='*60}\n3 ARQUITETURAS — mesmo projeto (~650 LOC, sonnet)\n{'='*60}", flush=True)
    print(f"  A monólito puro      ${custo_a:.4f}   (1 boot, {mid['raw']['meta']['turns']} turns)", flush=True)
    print(f"  B dispatcher frio    ${custo_b:.4f}   ({mid['orch']['meta']['n_tasks']} sessões frias)", flush=True)
    print(f"  C sessão+subagentes  ${custo_c:.4f}   (1 sessão, {r.get('num_turns')} turns principais)", flush=True)
    print(f"\n  C/A = {custo_c/custo_a:.2f}x   ·   C/B = {custo_c/custo_b:.2f}x", flush=True)
    print("\n(custo = total_cost_usd, agrega subagentes; tokens da thread principal abaixo)", flush=True)
    print(f"  C tokens(principal): {tok}", flush=True)

    out = Path(__file__).parent / "_resultado_C.json"
    out.write_text(json.dumps(
        {"dir": pasta, "custo_C": custo_c, "tokens_principal_C": tok,
         "turns_C": r.get("num_turns"), "custo_A": custo_a, "custo_B": custo_b},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultado salvo em {out}\nAvalie a qualidade em {pasta}", flush=True)


if __name__ == "__main__":
    main()
