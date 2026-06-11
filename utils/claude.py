import json
import re
import subprocess
import sys

_ON_WINDOWS = sys.platform == "win32"
_CLAUDE_CMD = ["wsl.exe", "claude", "-p"] if _ON_WINDOWS else ["claude", "-p"]


class ClaudeError(Exception):
    pass


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


def run_prompt(prompt: str, timeout: int = 120) -> dict:
    """Run a prompt via `claude -p` and return parsed JSON output."""
    try:
        result = subprocess.run(
            _CLAUDE_CMD + [prompt],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as e:
        raise ClaudeError("claude CLI not found — make sure Claude Code is installed") from e
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
