from pathlib import Path


def check_conflicts(files: dict[str, str], pasta: str) -> list[str]:
    """Return the relative paths in `files` that already exist under `pasta`."""
    root = Path(pasta)
    return [rel_path for rel_path in files if (root / rel_path).exists()]


def write(files: dict[str, str], pasta: str) -> None:
    """Write each {relative_path: content} entry under `pasta`."""
    root = Path(pasta)
    root.mkdir(parents=True, exist_ok=True)

    for rel_path, content in files.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n" — sem isso o Windows grava CRLF e os scripts bash quebram no WSL
        target.write_text(content, encoding="utf-8", newline="\n")
