#!/usr/bin/env bash
# Tear down the agent-talk session. Idempotent — safe to run anytime.
#   - close the chat pane (read-only renderer; nothing is lost)
#   - by default LEAVE the follow-reader running so the user keeps receiving
#     between sessions (mirrors start.sh's "exactly one" design).
# Usage:
#   ./stop.sh            # close chat pane only (normal session end)
#   ./stop.sh --reader   # ALSO stop the follow-reader (go offline)
#   ./stop.sh --all      # alias for --reader
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.sh"

SUP_PAT="$AT_SUP_PAT"           # this identity's follow-reader (scoped, from config)
TITLE="${AT_USER}·chat"         # tmux title of the chat pane

STOP_READER=0
case "${1:-}" in
  --reader|--all) STOP_READER=1 ;;
  "" ) ;;
  * ) echo "usage: ./stop.sh [--reader|--all]" >&2; exit 2 ;;
esac

# ---- chat pane ----
if [ -n "${TMUX:-}" ]; then
  pane=$(tmux list-panes -F '#{pane_id} #{pane_title}' \
    | awk -v t="$TITLE" '$2==t{print $1; exit}')
  if [ -n "$pane" ]; then
    tmux kill-pane -t "$pane"
    echo "chat pane: closed ($pane)"
  else
    echo "chat pane: none open"
  fi
else
  echo "chat pane: skipped (not inside tmux)"
fi

# ---- follow-reader (optional) ----
if [ "$STOP_READER" -eq 1 ]; then
  pids=$(pgrep -f "$SUP_PAT" || true)
  if [ -z "$pids" ]; then
    echo "follow-reader: none running"
  else
    for pid in $pids; do
      pkill -P "$pid" 2>/dev/null || true   # the retalk receive child FIRST
      kill "$pid" 2>/dev/null || true       # then the supervisor loop
    done
    echo "follow-reader: stopped ($(echo $pids | wc -w | tr -d ' ') supervisor(s))"
  fi
else
  echo "follow-reader: left running (use --reader to stop; $AT_USER stays reachable)"
fi
