"""Seletor nativo de pasta via tkinter rodando em um subprocess.

Nota: o subprocess aqui invoca Python/tkinter (diálogo nativo do SO),
não o Claude Code — por isso este módulo não passa por `utils/claude.py`.
"""

import os
import subprocess
import sys
import tempfile

_ON_WINDOWS = sys.platform == "win32"

# Quando rodando no WSL, usa o Python do Windows para abrir o diálogo nativo.
_PYWIN = (
    sys.executable
    if _ON_WINDOWS
    else "/mnt/c/Users/brend/AppData/Local/Programs/Python/Python310/python.exe"
)

# Tempo máximo (segundos) que o diálogo pode ficar aberto.
_TIMEOUT = 120

_SCRIPT = """\
import os
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.wm_attributes('-topmost', True)
folder = filedialog.askdirectory(parent=root, title='Escolha a pasta do projeto')
root.destroy()
if folder:
    print(os.path.normpath(folder))
"""


class FolderPickerTimeout(Exception):
    """Lançada quando o diálogo fica aberto além do timeout."""


def _to_win_path(path: str) -> str:
    """Converte um path WSL (/mnt/c/...) para path Windows (C:\\...)."""
    if not _ON_WINDOWS and path.startswith("/mnt/"):
        parts = path[5:].split("/", 1)
        drive = parts[0].upper() + ":\\"
        rest = parts[1].replace("/", "\\") if len(parts) > 1 else ""
        return drive + rest
    return path


def pick_folder() -> str:
    """Abre o diálogo nativo e retorna o path escolhido, ou "" se cancelado.

    Raises:
        FolderPickerTimeout: se o usuário não escolher dentro de `_TIMEOUT`.
    """
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8",
        ) as f:
            f.write(_SCRIPT)
            script_path = f.name

        try:
            result = subprocess.run(
                [_PYWIN, _to_win_path(script_path)],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise FolderPickerTimeout(
                f"Diálogo de seleção de pasta excedeu {_TIMEOUT}s"
            ) from exc

        return result.stdout.strip()
    finally:
        if script_path:
            try:
                os.unlink(script_path)
            except Exception:
                pass
