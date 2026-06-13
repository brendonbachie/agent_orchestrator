"""Cache do resultado da análise, por hash da descrição + templates.

Gerar o mesmo projeto duas vezes não deve custar tokens de novo: a chave é
determinística e o valor é o dict pronto de :func:`core.analyzer.analyze`.
Fica em ``~/.orchestrator/cache`` (mesma raiz de estado do app, como o
``storage.py``).
"""

import hashlib
import json
from pathlib import Path

_CACHE_DIR = Path.home() / ".orchestrator" / "cache"


def cache_key(descricao: str, templates: list[str]) -> str:
    raw = json.dumps({"d": descricao, "t": templates}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_get(key: str) -> dict[str, object] | None:
    f = _CACHE_DIR / f"{key}.json"
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def cache_set(key: str, value: dict[str, object]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (_CACHE_DIR / f"{key}.json").write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass
