#!/usr/bin/env bash
# Bootstrap the agent-talk session. Idempotent — safe to run every session.
#   1) ensure EXACTLY ONE follow-reader is feeding the inbox (relay -> spool)
#   2) open the colorful chat pane (if not already open)
# Identity/relay/peer come from config.sh.
# Usage: ./start.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.sh"

# A follow-reader supervisor is the bash loop whose argv mentions both --follow
# and this identity's inbox path. The retalk child does NOT carry the inbox path
# in its argv, so AT_SUP_PAT matches supervisors only — and scopes to this user.
# Paths are EXPANDED into the loop string (not passed via env) precisely so they
# appear in argv where pgrep can see them.
start_reader() {
  local cmd="while true; do retalk receive --peer '$AT_PEER' --follow --dir '$AT_IDDIR' >> '$AT_INBOX' 2>> '$AT_BASE/follow.err'; sleep 2; done"
  nohup bash -c "$cmd" >/dev/null 2>&1 &
  disown 2>/dev/null || true
}

# ---- 1) exactly one follow-reader ----
pids=$(pgrep -f "$AT_SUP_PAT" || true)
set -- $pids
n=$#
if [ "$n" -eq 0 ]; then
  start_reader
  echo "follow-reader: started (none was running)"
elif [ "$n" -gt 1 ]; then
  first=$1; shift
  for pid in "$@"; do
    pkill -P "$pid" 2>/dev/null || true   # kill its retalk child
    kill "$pid" 2>/dev/null || true       # kill the supervisor loop
  done
  echo "follow-reader: reaped $((n - 1)) duplicate(s), kept PID $first"
else
  echo "follow-reader: ok (PID $1)"
fi

# ---- 2) chat pane ----
if [ -n "${TMUX:-}" ]; then
  "$DIR/open-chat.sh" || true
else
  echo "chat pane: skipped (not inside tmux)" >&2
fi

# ---- info: relay reachability (non-fatal) ----
code=$(curl -sS -m 6 -o /dev/null -w '%{http_code}' \
  "$AT_RELAY/" 2>/dev/null || echo "down")
echo "relay: $code (anything but 'down' means reachable)"
echo "ready — send with: $DIR/send.sh $AT_PEER \"<text>\""

# ---- visual status overview (always shown on startup) ----
"$DIR/status.sh" || true
