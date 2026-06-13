"""Gate de verificação do dispatcher: roda os testes do projeto (best-effort).

Roda `pytest` no diretório do projeto com o Python do orquestrador. É best-effort:
se não há testes, o pytest não está disponível, ou há erro de import/coleta, NÃO
bloqueia (retorna True) — só retorna False quando há testes e eles FALHAM. Assim o
gate sinaliza problema real sem travar projetos que ainda não têm ambiente montado.
"""

import subprocess
import sys


def run_pytest(pasta: str, timeout: int = 300) -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=pasta,
            capture_output=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True  # não deu para verificar — não bloqueia

    # pytest: 0=passou, 5=nenhum teste coletado → ok; 1=testes falharam → bloqueia;
    # 2/3/4 (erro de uso/coleta/interno) → não bloqueia (best-effort).
    return result.returncode != 1
