#!/usr/bin/env bash
# =============================================================================
# pre-bash.sh — Hook PreToolUse (matcher: Bash)
#
# Bloqueia comandos perigosos ANTES de o Claude Code executá-los.
#
# Como o Claude Code chama este hook:
#   - O JSON do evento chega pelo stdin, no formato:
#       {
#         "hook_event_name": "PreToolUse",
#         "tool_name": "Bash",
#         "tool_input": { "command": "rm -rf /", "description": "..." },
#         ...
#       }
#   - Exit code 0 → comando liberado (stdout vai pro transcript em modo verbose)
#   - Exit code 2 → comando BLOQUEADO; o stderr é devolvido ao Claude como
#                   explicação do bloqueio
#
# Registro em .claude/settings.json:
#   {
#     "hooks": {
#       "PreToolUse": [
#         {
#           "matcher": "Bash",
#           "hooks": [
#             { "type": "command", "command": "bash templates/hooks/pre-bash.sh" }
#           ]
#         }
#       ]
#     }
#   }
# =============================================================================
set -uo pipefail

# --- 1. Lê o JSON do stdin e extrai tool_input.command -----------------------
INPUT="$(cat)"

if command -v jq >/dev/null 2>&1; then
    COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"
else
    # Fallback sem jq: usa Python (python3 ou python, o que existir)
    PY="$(command -v python3 || command -v python || true)"
    if [ -z "$PY" ]; then
        # Sem jq e sem Python não dá pra inspecionar o comando — libera.
        exit 0
    fi
    COMMAND="$(printf '%s' "$INPUT" | "$PY" -c '
import json, sys
data = json.load(sys.stdin)
print(data.get("tool_input", {}).get("command", ""))
')"
fi

# Sem comando, nada a validar.
[ -z "$COMMAND" ] && exit 0

# --- 2. Padrões perigosos (regex estendida, avaliados com grep -E) ------------
# Cobre: rm recursivo em raiz/home, push forçado, formatação de disco,
# escrita direta em devices, chmod 777 na raiz, fork bomb e "curl | sh".
PADROES=(
    'rm[[:space:]]+-[a-zA-Z]*[rR][a-zA-Z]*[[:space:]]+/([[:space:]]|$)'
    'rm[[:space:]]+-[a-zA-Z]*[rR][a-zA-Z]*[[:space:]]+/\*'
    'rm[[:space:]]+-[a-zA-Z]*[rR][a-zA-Z]*[[:space:]]+~([[:space:]]|/[[:space:]]*$|$)'
    'rm[[:space:]]+-[a-zA-Z]*[rR][a-zA-Z]*[[:space:]]+"?\$HOME"?([[:space:]]|$)'
    'git[[:space:]]+push[[:space:]].*--force([[:space:]]|$)'
    'git[[:space:]]+push[[:space:]].*[[:space:]]-f([[:space:]]|$)'
    'mkfs(\.[a-z0-9]+)?[[:space:]]'
    'dd[[:space:]].*of=/dev/'
    '>[[:space:]]*/dev/sd[a-z]'
    'chmod[[:space:]]+(-R[[:space:]]+)?777[[:space:]]+/([[:space:]]|$)'
    ':\(\)[[:space:]]*\{[[:space:]]*:\|:&[[:space:]]*\}[[:space:]]*;[[:space:]]*:'
    '(curl|wget)[^|]*\|[[:space:]]*(sudo[[:space:]]+)?(ba|z)?sh'
)

# --- 3. Verifica o comando contra cada padrão ---------------------------------
for padrao in "${PADROES[@]}"; do
    if printf '%s' "$COMMAND" | grep -Eq "$padrao"; then
        # exit 2 = bloqueia a ferramenta; stderr vira o feedback pro Claude.
        {
            echo "Comando bloqueado pelo hook pre-bash.sh (padrão perigoso detectado)."
            echo "Padrão: $padrao"
            echo "Comando: $COMMAND"
            echo "Se isso for realmente necessário, peça confirmação explícita ao usuário."
        } >&2
        exit 2
    fi
done

# Nenhum padrão perigoso encontrado — libera a execução.
exit 0
