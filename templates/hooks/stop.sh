#!/usr/bin/env bash
# =============================================================================
# stop.sh — Hook Stop
#
# Roda quando o Claude Code termina um turno (para de responder).
# Exemplo simples e reutilizável: emite uma notificação de fim de turno.
#
# Como o Claude Code chama este hook:
#   - O JSON do evento chega pelo stdin, no formato:
#       {
#         "hook_event_name": "Stop",
#         "session_id": "...",
#         "stop_hook_active": false,
#         ...
#       }
#   - Exit code 0 → encerra normalmente
#   - Exit code 2 → IMPEDE o Claude de parar e devolve o stderr como
#                   instrução (cuidado: use só com "stop_hook_active"
#                   pra não criar loop infinito). Este exemplo sempre sai 0.
#
# Registro em .claude/settings.json:
#   {
#     "hooks": {
#       "Stop": [
#         {
#           "hooks": [
#             { "type": "command", "command": "bash templates/hooks/stop.sh" }
#           ]
#         }
#       ]
#     }
#   }
# =============================================================================
set -uo pipefail

# Consome o stdin (o JSON do evento) — aqui só pra não deixar pipe pendurado.
INPUT="$(cat 2>/dev/null || true)"

MSG="Claude Code terminou o turno em $(date '+%H:%M:%S')."

# --- Notificação do sistema, se disponível, com fallback silencioso ----------
if command -v notify-send >/dev/null 2>&1; then
    # Linux com desktop (libnotify)
    notify-send "Claude Code" "$MSG" 2>/dev/null || true
elif command -v osascript >/dev/null 2>&1; then
    # macOS
    osascript -e "display notification \"$MSG\" with title \"Claude Code\"" \
        2>/dev/null || true
elif command -v powershell.exe >/dev/null 2>&1; then
    # Windows / WSL: um beep curto como aviso
    powershell.exe -NoProfile -Command "[console]::beep(800,200)" \
        >/dev/null 2>&1 || true
fi
# Sem nenhum mecanismo de notificação: segue em silêncio (fallback).

# Resumo no stderr — aparece no transcript em modo verbose (Ctrl+R).
echo "[stop.sh] $MSG" >&2

exit 0
