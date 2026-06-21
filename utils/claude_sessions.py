"""Acesso ao transcript de sessão do Claude Code de um projeto.

O Claude Code grava cada sessão em ``~/.claude/projects/<dir>/*.jsonl``, onde
``<dir>`` é o caminho de trabalho com todo caractere não-alfanumérico trocado por
``-`` (regra verificada empiricamente). Como o build roda no WSL, o caminho usado
é o WSL (``/mnt/c/...``). Este módulo localiza e lê esse transcript.

O subprocess aqui é leitura de arquivo no WSL (não invoca o Claude) — mesma
exceção de convenção do ``core/folderpicker.py``.
"""

import re
import subprocess
import sys
from pathlib import Path

_ON_WINDOWS = sys.platform == "win32"


def to_wsl_path(path: str) -> str:
    """Converte um caminho Windows (C:\\foo) para o ponto de montagem WSL (/mnt/c/foo)."""
    m = re.match(r"^([A-Za-z]):[/\\](.*)", path)
    if not m:
        return path
    drive = m.group(1).lower()
    rest = m.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def encode_session_dirname(pasta_wsl: str) -> str:
    """Nome do diretório de sessão do Claude para um caminho de trabalho WSL."""
    return re.sub(r"[^A-Za-z0-9]", "-", pasta_wsl)


def read_session_jsonl(pasta_wsl: str) -> str:
    """Retorna o conteúdo concatenado dos ``*.jsonl`` da sessão, ou ``""``.

    Inclui os transcripts dos SUBAGENTES (``<sessão>/subagents/*.jsonl``), gravados
    em subpasta separada da thread principal. Sem eles o consumo fica subestimado:
    medimos um build (projeto "tela") em que os subagentes eram ~28% do custo e o
    endpoint os ignorava — a "cegueira de sidechain". Como ``aggregate`` soma por
    modelo, basta concatenar os arquivos extras.

    Em Windows lê via WSL (onde o Claude rodou); em POSIX lê direto de
    ``~/.claude/projects``. Nunca lança — ausência de sessão retorna string vazia.
    """
    encoded = encode_session_dirname(pasta_wsl)

    if _ON_WINDOWS:
        # `encoded` só tem [A-Za-z0-9-], então é seguro interpolar no comando.
        base = f"~/.claude/projects/{encoded}"
        try:
            result = subprocess.run(
                ["wsl.exe", "bash", "-lc",
                 f"cat {base}/*.jsonl {base}/*/subagents/*.jsonl 2>/dev/null"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    base_dir = Path.home() / ".claude" / "projects" / encoded
    if not base_dir.exists():
        return ""
    partes: list[str] = []
    # Sessões principais + subagentes (subpasta `*/subagents/`), em ordem estável.
    arquivos = sorted(base_dir.glob("*.jsonl")) + sorted(base_dir.glob("*/subagents/*.jsonl"))
    for f in arquivos:
        try:
            partes.append(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(partes)
