"""Escreve o scaffold do RAG (do cache da geração) em disco, já com os tiers de
modelo injetados no frontmatter dos agentes pelo builder novo."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core import builder, writer  # noqa: E402

TARGET = r"C:\Users\brend\OneDrive\Área de Trabalho\RAG3"

cdir = Path.home() / ".orchestrator" / "cache"
cf = max(cdir.glob("*.json"), key=lambda p: p.stat().st_mtime)
r = json.loads(cf.read_text(encoding="utf-8"))

files = builder.build(r["claude_md"], r["agentes"], r["hooks"], r["primeiro_prompt"], r["plano"])
writer.write(files, TARGET)
print("escrito em %s — %d arquivos" % (TARGET, len(files)))
print("\n=== frontmatter dos agentes (tier injetado) ===")
for k in sorted(files):
    if k.startswith(".claude/agents/"):
        head = files[k].splitlines()
        fm = head[: (head.index("---", 1) + 1 if "---" in head[1:] else 5)]
        model = next((line for line in fm if line.lower().startswith("model:")), "(sem model)")
        print("  %-40s -> %s" % (k.split("/")[-1], model))
