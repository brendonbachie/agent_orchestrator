import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

_DATA_DIR = Path.home() / ".orchestrator"
_DATA_FILE = _DATA_DIR / "projetos.json"

# Serializa o read-modify-write entre threads (os endpoints chamam via
# asyncio.to_thread), evitando lost update quando dois /generate caem juntos.
_LOCK = threading.Lock()


def save_project(pasta: str, files: list[str], primeiro_prompt: str) -> None:
    with _LOCK:
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
        _atomic_write(
            _DATA_FILE, json.dumps(projects, indent=2, ensure_ascii=False)
        )


def list_projects() -> list[dict]:
    return _load()


def _atomic_write(path: Path, content: str) -> None:
    """Grava via arquivo temporário + os.replace — sem janela de corrupção.

    Se o processo morrer no meio da escrita, o arquivo antigo permanece intacto;
    o conteúdo novo só aparece com o rename atômico no mesmo filesystem.
    """
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load() -> list[dict]:
    if not _DATA_FILE.exists():
        return []
    try:
        data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []
