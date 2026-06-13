import json
import os
import re
import subprocess
import sys
import tempfile

_ON_WINDOWS = sys.platform == "win32"
_CLAUDE_CMD = ["wsl.exe", "claude", "-p"] if _ON_WINDOWS else ["claude", "-p"]

_sandbox: str | None = None


class ClaudeError(Exception):
    pass


class ClaudeNotFound(ClaudeError):
    """CLI ausente — não adianta repetir."""


_ALLOWED_MODELS = {"sonnet", "opus", "haiku"}


def _safe_model(model: str | None) -> str | None:
    """Normaliza/valida o id de modelo antes de virar o argv ``--model``.

    Defesa contra *argument injection*: o ``modelo`` de cada task do plano é
    gerado pelo LLM (Prompt 3) e cai direto em ``--model <valor>``. Um valor
    começando com ``-`` (ex.: ``--dangerously-skip-permissions``) jamais pode
    chegar ao CLI como flag. Só passam tiers conhecidos; ``"free"`` (tier do
    roadmap #12, ainda sem roteamento) cai no tier real mais barato (sonnet) em
    vez de quebrar a chamada com um ``--model free`` inexistente.
    """
    if model is None:
        return None
    m = model.strip().lower()
    if m == "free":
        return "sonnet"
    if m not in _ALLOWED_MODELS:
        raise ClaudeError(f"modelo não permitido: {model!r}")
    return m


def _neutral_cwd() -> str:
    """Pasta vazia de onde rodar o `claude -p`.

    Sem isso, o `claude` herda o diretório do servidor (a pasta do orquestrador)
    e carrega o CLAUDE.md/.claude dele em TODA chamada — contexto irrelevante que
    medimos dobrar o custo de uma chamada. Uma pasta vazia (sem CLAUDE.md nos
    ancestrais) elimina esse vazamento.
    """
    global _sandbox
    if _sandbox is None:
        _sandbox = tempfile.mkdtemp(prefix="orchestrator-claude-")
    return _sandbox


def _extract_json(raw: str) -> object:
    """Parse the first complete JSON value in raw, ignoring prose and fences.

    Strategy: try json.loads on the whole output; then look inside a markdown
    fence (```json ... ```); finally raw_decode from the first { or [, which
    tolerates prose before and after the JSON value.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    candidates = []
    # Content of the first fenced block (closing fence optional)
    m = re.search(r"```(?:json)?\s*([\s\S]*?)(?:```|$)", raw)
    if m:
        candidates.append(m.group(1))
    candidates.append(raw)

    decoder = json.JSONDecoder()
    for text in candidates:
        starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
        if not starts:
            continue
        try:
            value, _ = decoder.raw_decode(text, min(starts))
            return value
        except json.JSONDecodeError:
            continue

    raise ClaudeError(f"claude -p returned non-JSON output: {raw[:300]}")


def _run_once(prompt: str, timeout: int, model: str | None) -> dict[str, object]:
    cmd = list(_CLAUDE_CMD)
    safe = _safe_model(model)
    if safe:
        cmd += ["--model", safe]
    try:
        # O prompt vai por stdin, nunca como argv: assim um prompt começando com
        # `-` (montado a partir da descrição do usuário) jamais é lido como flag
        # do CLI (argument injection).
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            cwd=_neutral_cwd(),
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as e:
        raise ClaudeNotFound("claude CLI not found — make sure Claude Code is installed") from e
    except subprocess.TimeoutExpired as e:
        raise ClaudeError(f"claude -p timed out after {timeout}s") from e

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ClaudeError(f"claude -p exited {result.returncode}: {stderr}")

    data = _extract_json(result.stdout.strip())
    if not isinstance(data, dict):
        raise ClaudeError(
            f"claude -p returned JSON of type {type(data).__name__}, expected an object"
        )
    return data


def run_prompt(
    prompt: str, timeout: int = 120, model: str | None = None, retries: int = 2
) -> dict[str, object]:
    """Run a prompt via `claude -p` and return parsed JSON output.

    ``model`` escolhe o modelo da chamada (ex.: ``"sonnet"``, ``"opus"``);
    ``None`` usa o default do Claude Code. Em falha transitória (timeout, exit
    não-zero, output não-JSON) repete até ``retries`` vezes — uma única falha não
    derruba a cadeia de 3 prompts. CLI ausente (``ClaudeNotFound``) não repete.
    """
    erro: ClaudeError | None = None
    for _ in range(retries + 1):
        try:
            return _run_once(prompt, timeout, model)
        except ClaudeNotFound:
            raise
        except ClaudeError as e:
            erro = e
    assert erro is not None
    raise erro


def run_task(prompt: str, model: str, cwd: str, timeout: int = 1800) -> dict[str, object]:
    """Executa uma TASK de build via `claude -p`, no diretório do projeto.

    Diferente de `run_prompt`: roda em ``cwd`` (o projeto — para enxergar o CLAUDE.md
    e os arquivos das tasks anteriores), grava arquivos (``acceptEdits``) e devolve o
    uso de tokens, sem exigir JSON no conteúdo. É o runner de produção do dispatcher;
    cada task é uma sessão separada → contexto isolado.
    """
    cmd = list(_CLAUDE_CMD) + [
        "--model", model,
        "--permission-mode", "acceptEdits",
        "--output-format", "json",
    ]
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            cwd=cwd,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as e:
        raise ClaudeNotFound("claude CLI not found — make sure Claude Code is installed") from e
    except subprocess.TimeoutExpired as e:
        raise ClaudeError(f"task excedeu {timeout}s") from e

    if result.returncode != 0:
        raise ClaudeError(f"claude -p exited {result.returncode}: {result.stderr.strip()[:300]}")

    try:
        env = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ClaudeError("claude -p não retornou JSON de resultado (--output-format json)") from e

    return {
        "ok": not env.get("is_error", False),
        "usage": env.get("usage", {}),
        "cost_usd": env.get("total_cost_usd"),
        "num_turns": env.get("num_turns"),
    }
