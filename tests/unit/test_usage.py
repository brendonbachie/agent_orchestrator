import json

from core.usage import aggregate


def _msg(inp=0, cre=0, rea=0, out=0):
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": inp,
                    "cache_creation_input_tokens": cre,
                    "cache_read_input_tokens": rea,
                    "output_tokens": out,
                }
            },
        }
    )


def test_aggregate_empty_text():
    r = aggregate("")
    assert r["encontrado"] is False
    assert r["total"] == 0
    assert r["mensagens"] == 0


def test_aggregate_sums_usage():
    text = "\n".join([_msg(inp=10, cre=100, rea=1000, out=5),
                       _msg(inp=20, cre=200, rea=2000, out=7)])
    r = aggregate(text)
    assert r["encontrado"] is True
    assert r["mensagens"] == 2
    assert r["input_fresco"] == 30
    assert r["cache_creation"] == 300
    assert r["cache_read"] == 3000
    assert r["output"] == 12
    assert r["total_entrada"] == 30 + 300 + 3000
    assert r["total"] == 30 + 300 + 3000 + 12


def test_aggregate_ignores_lines_without_usage():
    text = "\n".join([
        json.dumps({"type": "mode"}),
        json.dumps({"type": "user", "message": {"content": "oi"}}),
        _msg(out=3),
    ])
    r = aggregate(text)
    assert r["mensagens"] == 1
    assert r["output"] == 3


def test_aggregate_skips_malformed_lines():
    text = "\n".join(["{ not json", "", _msg(inp=5), "lixo aqui"])
    r = aggregate(text)
    assert r["mensagens"] == 1
    assert r["input_fresco"] == 5


def test_aggregate_tolerates_missing_fields():
    text = json.dumps({"message": {"usage": {"output_tokens": 9}}})
    r = aggregate(text)
    assert r["output"] == 9
    assert r["input_fresco"] == 0


def test_aggregate_computes_usd_cost_opus():
    text = json.dumps({"message": {"model": "claude-opus-4-8", "usage": {
        "input_tokens": 1_000_000, "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0, "output_tokens": 0}}})
    r = aggregate(text)
    assert r["custo_usd"] == 15.0  # 1M input em Opus = $15
    assert r["modelos"] == ["claude-opus-4-8"]


def test_aggregate_cost_zero_for_unknown_model():
    text = json.dumps({"message": {"model": "llama-free", "usage": {
        "input_tokens": 1_000_000}}})
    r = aggregate(text)
    assert r["custo_usd"] == 0.0
