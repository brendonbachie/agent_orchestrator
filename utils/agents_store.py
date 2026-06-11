import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_TEMPLATES_DIR = _PROJECT_ROOT / "templates" / "agents"
GLOBAL_AGENTS_DIR = _PROJECT_ROOT.parent / "agents"

_DATA_DIR = Path.home() / ".orchestrator"
_PINNED_FILE = _DATA_DIR / "pinned_agents.json"


def list_agents() -> list[dict]:
    seen: dict[str, dict] = {}

    if _TEMPLATES_DIR.exists():
        for f in sorted(_TEMPLATES_DIR.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            seen[f.stem] = {
                "name": f.stem,
                "description": _extract_description(content),
                "source": "biblioteca",
                "conteudo": content,
                "pinned": False,
            }

    if GLOBAL_AGENTS_DIR.exists():
        for f in sorted(GLOBAL_AGENTS_DIR.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            seen[f.stem] = {
                "name": f.stem,
                "description": _extract_description(content),
                "source": "global",
                "conteudo": content,
                "pinned": False,
            }

    pinned = set(_load_pinned())
    for name in pinned:
        if name in seen:
            seen[name]["pinned"] = True

    return list(seen.values())


def save_agent(name: str, content: str) -> None:
    GLOBAL_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    (GLOBAL_AGENTS_DIR / f"{name}.md").write_text(content, encoding="utf-8")


def save_agents_from_files(files: dict[str, str]) -> None:
    for path, content in files.items():
        if path.startswith(".claude/agents/") and path.endswith(".md"):
            save_agent(Path(path).stem, content)


def set_pinned(name: str, pinned: bool) -> None:
    pinned_list = _load_pinned()
    if pinned and name not in pinned_list:
        pinned_list.append(name)
    elif not pinned and name in pinned_list:
        pinned_list.remove(name)
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _PINNED_FILE.write_text(
        json.dumps(pinned_list, ensure_ascii=False), encoding="utf-8"
    )


def _extract_description(content: str) -> str:
    for line in content.strip().splitlines()[1:]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _load_pinned() -> list[str]:
    if not _PINNED_FILE.exists():
        return []
    try:
        data = json.loads(_PINNED_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []
