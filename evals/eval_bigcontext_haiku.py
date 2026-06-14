"""Eval do REGIME GRANDE — projeto que enche a janela de contexto (Haiku, 200k).

~30 módulos utilitários INDEPENDENTES (~180 funções). Construído de duas formas, em
Haiku (barato → o regime grande fica testável no Pro):
  RAW  — um único `claude` com o spec inteiro (monólito). Acumula os 30 módulos numa
         sessão → empurra o contexto pra perto/além de 200k → deve COMPACTAR (esquecer
         módulos do começo) ou bater o limite de turnos e parar incompleto.
  ORCH — dispatcher: 30 tasks frias, cada uma só com o seu módulo → fica pequena.

Hipótese (regime onde isolar VENCE): o monólito degrada/incompleta enquanto o
dispatcher completa tudo. Mede CUSTO + COMPLETUDE (medida depois: nº de módulos e
pytest nas duas pastas).

Rodar:  python evals/eval_bigcontext_haiku.py   (build grande; ~60-90 min; gasta cota)
"""

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.dispatcher import ordenar, prompt_da_task  # noqa: E402
from utils.claude import run_task  # noqa: E402

MODEL = "haiku"

# (nome, [assinaturas/descrições curtas de funções])
MODULOS: list[tuple[str, list[str]]] = [
    ("strings", ["slugify(s)", "truncate(s,n)", "pad_left(s,n,c)", "count_words(s)", "reverse_words(s)", "is_palindrome(s)"]),
    ("datas", ["dias_entre(d1,d2)", "eh_fim_de_semana(d)", "formata_br(d)", "proximo_dia_util(d)", "idade(nasc,hoje)", "mes_nome(n)"]),
    ("numeros", ["arredonda(x,casas)", "clamp(x,lo,hi)", "porcentagem(p,total)", "formata_moeda(x)", "mdc(a,b)", "mmc(a,b)"]),
    ("listas", ["chunk(lst,n)", "achata(lst)", "unicos(lst)", "agrupa_por(lst,key)", "particiona(lst,pred)", "rotaciona(lst,n)"]),
    ("dicts", ["deep_get(d,path)", "inverte(d)", "filtra_chaves(d,keys)", "mescla(a,b)", "pega(d,keys)", "omite(d,keys)"]),
    ("validacao", ["eh_email(s)", "eh_cpf(s)", "eh_telefone(s)", "eh_url(s)", "eh_cep(s)", "senha_forte(s)"]),
    ("texto", ["title_case(s)", "snake_para_camel(s)", "camel_para_snake(s)", "remove_acentos(s)", "quebra_linha(s,n)", "conta_vogais(s)"]),
    ("caminhos", ["junta(*p)", "extensao(p)", "nome_base(p)", "troca_ext(p,ext)", "sanitiza_nome(s)", "eh_oculto(p)"]),
    ("cores", ["hex_para_rgb(h)", "rgb_para_hex(r,g,b)", "clareia(h,f)", "escurece(h,f)", "luminancia(h)", "contraste(h1,h2)"]),
    ("estatistica", ["media(xs)", "mediana(xs)", "moda(xs)", "desvio_padrao(xs)", "percentil(xs,p)", "amplitude(xs)"]),
    ("codificacao", ["b64_encode(s)", "b64_decode(s)", "url_encode(s)", "html_escape(s)", "rot13(s)", "hex_encode(s)"]),
    ("tempo", ["formata_duracao(seg)", "parse_duracao(s)", "humaniza(seg)", "eh_bissexto(ano)", "dias_no_mes(ano,mes)", "trimestre(mes)"]),
    ("matriz", ["transpoe(m)", "multiplica(a,b)", "identidade(n)", "soma(a,b)", "escala(m,k)", "eh_quadrada(m)"]),
    ("intervalos", ["sobrepoe(a,b)", "mescla_intervalos(lst)", "contem(intv,x)", "tamanho(intv)", "interseccao(a,b)", "uniao(a,b)"]),
    ("financas", ["juros_compostos(p,t,n)", "parcelas(total,n,j)", "desconto(v,p)", "valor_presente(f,t,n)", "roi(g,c)", "margem(v,c)"]),
    ("conversao", ["cm_para_pol(cm)", "kg_para_lb(kg)", "c_para_f(c)", "km_para_milhas(km)", "l_para_gal(l)", "bytes_humano(n)"]),
    ("aleatorio", ["escolhe(lst,seed)", "embaralha(lst,seed)", "senha_gen(n,seed)", "dado(faces,seed)", "entre(a,b,seed)", "amostra(lst,k,seed)"]),
    ("csv", ["parse_linha(s)", "escapa(campo)", "para_dict(headers,linha)", "junta_linha(campos)", "conta_colunas(s)", "valida_linha(s,n)"]),
    ("cpf_cnpj", ["valida_cpf(s)", "valida_cnpj(s)", "formata_cpf(s)", "formata_cnpj(s)", "so_digitos(s)", "mascara(s,n)"]),
    ("json_utils", ["caminho_get(obj,path)", "achata_json(obj)", "merge_json(a,b)", "remove_nulos(obj)", "conta_chaves(obj)", "profundidade(obj)"]),
    ("url_utils", ["parse_query(s)", "monta_query(d)", "junta_url(base,path)", "pega_dominio(u)", "eh_https(u)", "remove_fragmento(u)"]),
    ("tabela", ["largura_colunas(linhas)", "formata_tabela(linhas)", "ordena_por(linhas,col)", "filtra(linhas,pred)", "soma_coluna(linhas,col)", "media_coluna(linhas,col)"]),
    ("cache_lru", ["cria(cap)", "get(c,k)", "put(c,k,v)", "remove(c,k)", "tamanho(c)", "limpa(c)"]),
    ("pilha_fila", ["pilha_push(p,v)", "pilha_pop(p)", "fila_enqueue(f,v)", "fila_dequeue(f)", "topo(p)", "vazio(s)"]),
    ("arvore", ["insere(raiz,v)", "busca(raiz,v)", "altura(raiz)", "em_ordem(raiz)", "conta(raiz)", "minimo(raiz)"]),
    ("grafo", ["adiciona_aresta(g,a,b)", "vizinhos(g,n)", "bfs(g,ini)", "dfs(g,ini)", "tem_caminho(g,a,b)", "grau(g,n)"]),
    ("ordenacao", ["bubble(xs)", "quick(xs)", "merge_sort(xs)", "insertion(xs)", "eh_ordenado(xs)", "kth_menor(xs,k)"]),
    ("busca", ["binaria(xs,alvo)", "linear(xs,alvo)", "primeiro_maior(xs,x)", "conta_ocorrencias(xs,x)", "indices(xs,x)", "mais_proximo(xs,x)"]),
    ("bitmask", ["liga(m,i)", "desliga(m,i)", "testa(m,i)", "conta_bits(m)", "inverte_bits(m,n)", "mascara(n)"]),
    ("estado", ["cria(estados,trans)", "transiciona(m,evt)", "estado_atual(m)", "pode(m,evt)", "reseta(m)", "estados_alcancaveis(m)"]),
]

CONVENCOES = (
    "Convenções: cada módulo num arquivo <nome>.py com type hints e funções puras; "
    "entradas inválidas levantam ValueError; testes em tests/test_<nome>.py (pytest). "
    "Sem dependências externas além de pytest. Módulos são INDEPENDENTES entre si."
)


def spec_modulo(nome: str, funcs: list[str]) -> str:
    return f"Módulo `{nome}.py` — implemente: " + "; ".join(funcs) + "."


def spec_completo() -> str:
    blocos = [f"{i+1}. {spec_modulo(n, fs)}" for i, (n, fs) in enumerate(MODULOS)]
    return (
        "Construa uma biblioteca de utilitários em Python com os "
        f"{len(MODULOS)} módulos INDEPENDENTES abaixo, cada um com seus testes pytest.\n"
        + CONVENCOES + "\n\n" + "\n".join(blocos)
        + "\n\nImplemente TODOS os módulos e seus testes. Os testes devem passar."
    )


PLANO = [
    {"ordem": i + 1, "task": spec_modulo(n, fs) + " Inclua tests/test_" + n + ".py com pytest.",
     "contrato": f"{n}.py com as funções listadas; tests/test_{n}.py passa.",
     "agente": None, "modelo": MODEL, "depende_de": []}
    for i, (n, fs) in enumerate(MODULOS)
]

CLAUDE_MD = "# Toolkit de Utilitários\n\nBiblioteca Python pura (só pytest). " + CONVENCOES + "\n"


def _tokens(usage: dict) -> dict:
    return {"input": usage.get("input_tokens", 0),
            "cache_creation": usage.get("cache_creation_input_tokens", 0),
            "cache_read": usage.get("cache_read_input_tokens", 0),
            "output": usage.get("output_tokens", 0)}


def _somar(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in {"input", "cache_creation", "cache_read", "output"}}


def _retry(fn):
    for i in range(4):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            print(f"  falhou ({e}); retry {i+1}/4 backoff 45s", flush=True)
            if i == 3:
                raise
            time.sleep(45)


def run_raw(pasta: str) -> tuple[dict, float, dict]:
    print(f"\n── RAW monólito (haiku, spec de {len(MODULOS)} módulos) ──", flush=True)
    ini = time.monotonic()
    try:
        r = _retry(lambda: run_task(spec_completo(), MODEL, pasta, timeout=3600))
    except Exception as e:  # noqa: BLE001
        print(f"  ERRO: {e}", flush=True)
        return {}, 0.0, {"erro": str(e)}
    dt = time.monotonic() - ini
    print(f"  ok={r['ok']} turns={r.get('num_turns')} {dt:.0f}s cost=${r.get('cost_usd')}", flush=True)
    return _tokens(r.get("usage") or {}), float(r.get("cost_usd") or 0), {
        "ok": r.get("ok"), "turns": r.get("num_turns"), "segundos": round(dt)}


def run_orch(pasta: str) -> tuple[dict, float, dict]:
    print(f"\n── ORCH dispatcher (haiku, {len(PLANO)} tasks frias) ──", flush=True)
    Path(pasta, "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    tokens: dict = {}
    custo = 0.0
    feitas: list[dict] = []
    det = []
    for task in ordenar(PLANO):
        ini = time.monotonic()
        try:
            r = _retry(lambda t=task: run_task(prompt_da_task(t, []), MODEL, pasta, timeout=900))
        except Exception as e:  # noqa: BLE001
            print(f"  task {task['ordem']}: ERRO {e}", flush=True)
            det.append({"ordem": task["ordem"], "erro": str(e)})
            continue
        dt = time.monotonic() - ini
        print(f"  task {task['ordem']:>2} ({task['task'][:28]}): ok={r['ok']} "
              f"turns={r.get('num_turns')} {dt:.0f}s ${r.get('cost_usd')}", flush=True)
        tokens = _somar(tokens, _tokens(r.get("usage") or {}))
        custo += float(r.get("cost_usd") or 0)
        det.append({"ordem": task["ordem"], "ok": r.get("ok"), "turns": r.get("num_turns")})
        feitas.append(task)
    return tokens, custo, {"n_tasks": len(PLANO), "tasks": det}


def main() -> None:
    raw_dir = tempfile.mkdtemp(prefix="big-raw-")
    orch_dir = tempfile.mkdtemp(prefix="big-orch-")
    print(f"raw_dir  = {raw_dir}\norch_dir = {orch_dir}\nmódulos = {len(MODULOS)}", flush=True)

    rt, rc, rmeta = run_raw(raw_dir)
    ot, oc, ometa = run_orch(orch_dir)

    cols = ["input", "cache_creation", "cache_read", "output"]
    print(f"\n{'='*60}\nCUSTO (haiku, {len(MODULOS)} módulos)\n{'='*60}", flush=True)
    print(f"{'':18}{'RAW':>16}{'ORCH':>16}", flush=True)
    for c in cols:
        print(f"{c:18}{rt.get(c, 0):>16,}{ot.get(c, 0):>16,}", flush=True)
    tr, to = sum(rt.values()), sum(ot.values())
    print(f"{'TOTAL tokens':18}{tr:>16,}{to:>16,}", flush=True)
    print(f"{'custo USD':18}{rc:>16.4f}{oc:>16.4f}", flush=True)
    if tr and rc:
        print(f"\n  ORCH/RAW  →  tokens {to/tr:.2f}x   ·   custo {oc/rc:.2f}x", flush=True)
    print(f"\n  RAW: {rmeta}\n  ORCH n_tasks={ometa.get('n_tasks')}", flush=True)
    print("  >>> COMPLETUDE (módulos + pytest) avaliar nas pastas acima <<<", flush=True)

    (Path(__file__).parent / "_resultado_big.json").write_text(json.dumps(
        {"raw_dir": raw_dir, "orch_dir": orch_dir, "n_modulos": len(MODULOS),
         "raw": {"tokens": rt, "custo": rc, "meta": rmeta},
         "orch": {"tokens": ot, "custo": oc, "meta": ometa}},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nResultado salvo em evals/_resultado_big.json", flush=True)


if __name__ == "__main__":
    main()
