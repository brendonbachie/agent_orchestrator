"""Agregação do consumo de tokens de um transcript de sessão do Claude Code.

Função pura: recebe o texto JSONL e soma o uso reportado em cada mensagem do
assistente. Distingue input fresco, escrita/leitura de cache e output — a leitura
de cache (``cache_read``) costuma dominar o volume e custa ~10× menos.
"""

import json

_CAMPOS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)

# Preço de lista (USD por milhão de tokens) por família de modelo.
# cache_w = escrita de cache (~1,25× input); cache_r = leitura de cache (~0,1× input).
_PRECOS = {
    "opus": {"input": 15.0, "cache_w": 18.75, "cache_r": 1.5, "output": 75.0},
    "sonnet": {"input": 3.0, "cache_w": 3.75, "cache_r": 0.3, "output": 15.0},
    "haiku": {"input": 0.8, "cache_w": 1.0, "cache_r": 0.08, "output": 4.0},
}


def _tier(model: str) -> str | None:
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return None


def _custo_usd(por_modelo: dict[str, dict[str, int]]) -> float:
    total = 0.0
    for model, t in por_modelo.items():
        tier = _tier(model)
        if tier is None:
            continue
        p = _PRECOS[tier]
        total += (
            t["input_tokens"] * p["input"]
            + t["cache_creation_input_tokens"] * p["cache_w"]
            + t["cache_read_input_tokens"] * p["cache_r"]
            + t["output_tokens"] * p["output"]
        ) / 1_000_000
    return round(total, 4)


def aggregate(jsonl_text: str) -> dict[str, object]:
    tot = dict.fromkeys(_CAMPOS, 0)
    por_modelo: dict[str, dict[str, int]] = {}
    mensagens = 0

    for line in jsonl_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = o.get("message") or {}
        u = msg.get("usage")
        if not isinstance(u, dict):
            continue
        mensagens += 1
        modelo = msg.get("model") or "?"
        acc = por_modelo.setdefault(modelo, dict.fromkeys(_CAMPOS, 0))
        for k in _CAMPOS:
            v = u.get(k, 0)
            v = v if isinstance(v, int) else 0
            tot[k] += v
            acc[k] += v

    total_entrada = (
        tot["input_tokens"]
        + tot["cache_creation_input_tokens"]
        + tot["cache_read_input_tokens"]
    )
    return {
        "encontrado": mensagens > 0,
        "mensagens": mensagens,
        "input_fresco": tot["input_tokens"],
        "cache_creation": tot["cache_creation_input_tokens"],
        "cache_read": tot["cache_read_input_tokens"],
        "output": tot["output_tokens"],
        "total_entrada": total_entrada,
        "total": total_entrada + tot["output_tokens"],
        "custo_usd": _custo_usd(por_modelo),
        "modelos": sorted(m for m in por_modelo if m != "?"),
    }
