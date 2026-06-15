"""Força uma geração do orquestrador (RAG ~igual ao RAG2) e reporta o resultado.
O consumo é medido depois, pelos transcripts do cwd neutro."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.analyzer import analyze  # noqa: E402
import utils.claude as C  # noqa: E402

DESC = (
    "Quero um sistema RAG totalmente offline (sem internet) em Python para consultar "
    "manuais técnicos da Marinha (documentos VSNT em PDF). Usa Llama3 local via Ollama "
    "e banco vetorial ChromaDB com embeddings de sentence-transformers. Responde sempre "
    "em português, com temperature 0, e nunca inventa: se a informação não estiver nos "
    "trechos recuperados, diz que não encontrou e cita o manual/artigo de origem. Inclui "
    "ingestão de PDFs (inclusive escaneados com OCR), avaliação de qualidade da "
    "recuperação e geração ancorada."
)

t0 = time.monotonic()
r = analyze(DESC)
print("tempo: %ds" % round(time.monotonic() - t0), flush=True)
print("neutral_cwd:", C._sandbox, flush=True)
print("recomendacao:", r["recomendacao"], flush=True)
print("agentes:", [(a["name"], a["source"]) for a in r["agentes"]], flush=True)
print("plano (ordem | modelo | agente):", flush=True)
for t in r["plano"]:
    print("  %s | %-7s | %s" % (t.get("ordem"), t.get("modelo"), t.get("agente")), flush=True)
print("primeiro_prompt tem /clear?:", "/clear" in r["primeiro_prompt"], flush=True)
