import subprocess
import sys


def launch(pasta_wsl: str) -> None:
    """Open Claude Code via the generated .claude/launch.sh script.

    O prompt não passa pela linha de comando — o script lê
    .claude/primeiro-prompt.txt dentro do projeto. Isso evita que wt.exe/wsl.exe
    interpretem caracteres do prompt (wt trata ';' como separador de comandos).
    """
    script = f"{pasta_wsl}/.claude/launch.sh"

    if sys.platform == "win32":
        # Try Windows Terminal first
        try:
            subprocess.Popen([
                "wt.exe", "new-tab",
                "wsl.exe", "--",
                "bash", script.replace(";", "\\;"),
            ])
            return
        except FileNotFoundError:
            pass
        # Fallback: open WSL directly
        subprocess.Popen([
            "wsl.exe", "--",
            "bash", script,
        ])
    else:
        subprocess.Popen(
            ["bash", script],
            start_new_session=True,
        )
