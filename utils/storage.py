import json
from datetime import datetime, timezone
from pathlib import Path

_DATA_DIR = Path.home() / ".orchestrator"
_DATA_FILE = _DATA_DIR / "projetos.json"


def save_project(pasta: str, files: list[str], primeiro_prompt: str) -> None:
    projects = _load()
    projects.append(
        {
            "pasta": pasta,
            "files": files,
            "primeiro_prompt": primeiro_prompt,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
    )
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DATA_FILE.write_text(
        json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def list_projects() -> list[dict]:
    return _load()


def _load() -> list[dict]:
    if not _DATA_FILE.exists():
        return []
    try:
        data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []
