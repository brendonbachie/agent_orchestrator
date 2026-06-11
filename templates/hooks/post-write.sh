#!/usr/bin/env bash
# =============================================================================
# post-write.sh — Hook PostToolUse (matcher: Write|Edit)
#
# Roda `ruff check` em arquivos Python logo após o Claude Code escrevê-los
# ou editá-los. Se o ruff não estiver instalado, o hook sai em silêncio.
#
# Como o Claude Code chama este hook:
#   - O JSON do evento chega pelo stdin, no formato:
#       {
#         "hook_event_name": "PostToolUse",
#         "tool_name": "Write",
#         "tool_input": { "file_path": "/caminho/arquivo.py", "content": "..." },
#         "tool_response": { ... },
#         ...
#       }
#   - Exit code 0 → tudo certo, nada a reportar
#   - Exit code 2 → o stderr é devolvido ao Claude (a ferramenta já rodou,
#                   então não bloqueia — serve pra ele ver e corrigir o lint)
#
# Registro em .claude/settings.json:
#   {
#     "hooks": {
#       "PostToolUse": [
#         {
#           "matcher": "Write|Edit",
#           "hooks": [
#             { "type": "command", "command": "bash templates/hooks/post-write.sh" }
#           ]
#         }
#       ]
#     }
#   }
# =============================================================================
set -uo pipefail

# --- 1. Lê o JSON do stdin e extrai tool_input.file_path ----------------------
INPUT="$(cat)"

if command -v jq >/dev/null 2>&1; then
    FILE_PATH="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')"
else
    # Fallback sem jq: usa Python (python3 ou python, o que existir)
    PY="$(command -v python3 || command -v python || true)"
    if [ -z "$PY" ]; then
        exit 0
    fi
    FILE_PATH="$(printf '%s' "$INPUT" | "$PY" -c '
import json, sys
data = json.load(sys.stdin)
print(data.get("tool_input", {}).get("file_path", ""))
')"
fi

# --- 2. Só interessa arquivo Python existente ---------------------------------
[ -z "$FILE_PATH" ] && exit 0
case "$FILE_PATH" in
    *.py) ;;          # segue pro lint
    *) exit 0 ;;      # qualquer outra extensão: nada a fazer
esac
[ -f "$FILE_PATH" ] || exit 0

# --- 3. Roda ruff, se disponível (não falha se não estiver instalado) ---------
if ! command -v ruff >/dev/null 2>&1; then
    exit 0
fi

if ! SAIDA="$(ruff check "$FILE_PATH" 2>&1)"; then
    # exit 2 em PostToolUse não desfaz a escrita, mas manda o stderr
    # de volta pro Claude — assim ele vê os problemas e corrige.
    {
        echo "ruff encontrou problemas em $FILE_PATH:"
        echo "$SAIDA"
    } >&2
    exit 2
fi

exit 0
