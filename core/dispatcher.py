"""Executa o plano de tasks (do analyzer) task a task, em contexto isolado.

Cada task roda como uma sessão SEPARADA do Claude Code (via runner injetado), no
diretório do projeto. O contexto não se acumula entre tasks — ataca o cache_read,
que é o que mais custa — e cada task usa o modelo do seu tier (sonnet/opus). É a
execução FORÇADA da divisão; medimos que o prompt sozinho não garante a delegação.

A lógica aqui é pura (runner e gate são injetados) para ser testável sem chamar o
Claude. O runner de produção é `utils.claude.run_task`.
"""

from collections.abc import Callable

# runner(prompt, model, cwd) -> dict com pelo menos {"ok": bool, "usage": {...}}
Runner = Callable[[str, str, str], dict]
# gate(pasta) -> True se a verificação (ex.: testes) passou
Gate = Callable[[str], bool]


def ordenar(plano: list[dict]) -> list[dict]:
    """Ordena as tasks respeitando ``depende_de`` (ordenação topológica).

    Tasks sem dependências pendentes saem primeiro. Ciclos ou dependências
    inexistentes degradam com segurança: o restante sai na ordem de ``ordem``,
    em vez de travar.
    """
    tasks = sorted(plano, key=lambda t: t.get("ordem", 0))
    ordens_existentes = {t.get("ordem") for t in tasks}
    feitas: set = set()
    resultado: list[dict] = []
    restantes = list(tasks)

    while restantes:
        progrediu = False
        for t in list(restantes):
            deps = [d for d in (t.get("depende_de") or []) if d in ordens_existentes]
            if all(d in feitas for d in deps):
                resultado.append(t)
                feitas.add(t.get("ordem"))
                restantes.remove(t)
                progrediu = True
        if not progrediu:  # ciclo ou dependência impossível — emite o resto e para
            resultado.extend(restantes)
            break
    return resultado


def prompt_da_task(
    task: dict, feitas: list[dict], skills: list[str] | None = None
) -> str:
    """Monta o prompt focado de UMA task — enxuto, para o contexto não inchar.

    ``skills`` (nomes instalados em ``.claude/skills/``) são injetados à força no
    prompt: não confiamos no auto-trigger por description (medimos que o julgamento
    do modelo não delega de forma confiável) — instruímos a leitura do SKILL.md
    correspondente, do mesmo jeito que já forçamos o uso do agente.
    """
    partes = [
        "Você está implementando UMA task de um projeto maior. Leia o CLAUDE.md do "
        "projeto antes de começar e siga suas convenções.",
        "",
        f"TASK: {task.get('task', '')}",
    ]
    if task.get("contrato"):
        partes.append(
            f"CONTRATO (interface/saída que outras tasks vão consumir): {task['contrato']}"
        )
    agente = task.get("agente")
    if agente:
        partes.append(
            f"Aplique a especialidade do agente '{agente}' (.claude/agents/{agente}.md); "
            "abra um subagente com ele se ajudar."
        )
    if skills:
        nomes = ", ".join(skills)
        partes.append(
            f"Skills instaladas em .claude/skills/ ({nomes}): leia o SKILL.md da que "
            "corresponder à situação e siga-a. Em especial, antes de declarar a task "
            "concluída, VERIFIQUE de fato (rode os testes e leia a saída)."
        )
    if feitas:
        nomes = ", ".join(str(t.get("task", ""))[:50] for t in feitas)
        partes.append(f"Já implementado (não refaça): {nomes}")
    partes.append(
        "Implemente APENAS esta task, com seus testes. Não reescreva o resto do projeto."
    )
    return "\n".join(partes)


def dispatch(
    plano: list[dict],
    pasta: str,
    runner: Runner,
    gate: Gate | None = None,
    skills: list[str] | None = None,
) -> list[dict]:
    """Executa cada task em ordem topológica via ``runner``; ``gate`` opcional após cada uma.

    Retorna uma lista de resultados por task (ordem, task, modelo, agente + o que o
    runner devolver, e ``testes_ok`` se houver gate). ``skills`` (instaladas no
    projeto) são injetadas em cada prompt de task.
    """
    feitas: list[dict] = []
    resultados: list[dict] = []
    for task in ordenar(plano):
        modelo = task.get("modelo") or "sonnet"
        res = runner(prompt_da_task(task, feitas, skills), modelo, pasta)
        entrada: dict = {
            "ordem": task.get("ordem"),
            "task": task.get("task", ""),
            "modelo": modelo,
            "agente": task.get("agente"),
        }
        if isinstance(res, dict):
            entrada.update(res)
        if gate is not None:
            entrada["testes_ok"] = gate(pasta)
        resultados.append(entrada)
        feitas.append(task)
    return resultados
