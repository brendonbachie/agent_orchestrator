from core.dispatcher import dispatch, ordenar, prompt_da_task


def test_ordenar_respeita_dependencias():
    plano = [
        {"ordem": 3, "depende_de": [1, 2]},
        {"ordem": 1, "depende_de": []},
        {"ordem": 2, "depende_de": [1]},
    ]
    ordens = [t["ordem"] for t in ordenar(plano)]
    assert ordens.index(1) < ordens.index(2) < ordens.index(3)


def test_ordenar_quebra_ciclo_sem_travar():
    plano = [{"ordem": 1, "depende_de": [2]}, {"ordem": 2, "depende_de": [1]}]
    ordens = sorted(t["ordem"] for t in ordenar(plano))
    assert ordens == [1, 2]  # devolve todas, não entra em loop


def test_ordenar_ignora_dependencia_inexistente():
    assert [t["ordem"] for t in ordenar([{"ordem": 1, "depende_de": [99]}])] == [1]


def test_prompt_inclui_task_contrato_agente():
    p = prompt_da_task({"task": "fila", "contrato": "API X", "agente": "esp-fila"}, [])
    assert "fila" in p and "API X" in p and "esp-fila" in p
    assert "APENAS esta task" in p


def test_dispatch_executa_em_ordem_com_modelo_certo():
    chamadas = []

    def runner(prompt, model, cwd):
        chamadas.append((model, cwd))
        return {"ok": True, "usage": {"output_tokens": 1}}

    plano = [
        {"ordem": 2, "task": "b", "modelo": "sonnet", "depende_de": [1]},
        {"ordem": 1, "task": "a", "modelo": "opus", "depende_de": []},
    ]
    res = dispatch(plano, "/proj", runner)
    assert [r["ordem"] for r in res] == [1, 2]
    assert chamadas[0] == ("opus", "/proj")  # task 1 primeiro, em opus
    assert chamadas[1][0] == "sonnet"
    assert res[0]["ok"] is True


def test_dispatch_modelo_default_sonnet():
    res = dispatch([{"ordem": 1, "task": "x"}], "/p", lambda p, m, c: {"m": m})
    assert res[0]["modelo"] == "sonnet"


def test_dispatch_gate_registra_resultado():
    res = dispatch(
        [{"ordem": 1, "task": "x", "modelo": "sonnet"}],
        "/p",
        lambda p, m, c: {"ok": True},
        gate=lambda pasta: True,
    )
    assert res[0]["testes_ok"] is True
