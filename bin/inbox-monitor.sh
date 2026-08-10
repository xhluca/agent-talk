#!/usr/bin/env bash
# agent-talk inbox monitor (a Claude Code plugin monitor command).
#
# Pushes THIS session's user's incoming messages into the session: it resolves
# the user from the session->user map that `init` writes
# ($HOME/.agent-talk/by-session/<session-id>), then tails that session's spool,
# `<user>/sessions/<session-id>.ndjson`, which the spool writer fills.
#
# It also tails the older per-identity spool, `<user>/inbox.ndjson`, so a
# session whose follower predates the spool writer keeps delivering. Records
# reaching both files are emitted once: the dedupe below keys on the message id.
#
# $1 is ${CLAUDE_SESSION_ID}; if it did not substitute or is empty, it idles
# (push off — pull via the `receive` skill still works). Diagnostics to stderr;
# only message lines go to stdout.
set -uo pipefail
sid="${1:-}"
case "$sid" in ""|*'${'*) exec tail -f /dev/null;; esac      # no session id -> no push
sid="$(printf '%s' "$sid" | tr -c 'A-Za-z0-9._-' '_')"
map="$HOME/.agent-talk/by-session/$sid"
while [ ! -f "$map" ]; do sleep 2; done                      # init writes it after we start
udir="$(cat "$map")"
SESSION_SPOOL="$udir/sessions/$sid.ndjson"
LEGACY_SPOOL="$udir/inbox.ndjson"
mkdir -p "$udir/sessions" 2>/dev/null || true
: >> "$SESSION_SPOOL" 2>/dev/null || true
: >> "$LEGACY_SPOOL" 2>/dev/null || true

# Emit each message once, keyed on its id (falling back to the whole line for a
# record without one). fflush keeps the monitor line-live.
dedupe() {
  awk '{
    if (match($0, /"id"[[:space:]]*:[[:space:]]*"[^"]*"/)) {
      key = substr($0, RSTART, RLENGTH)
    } else {
      key = $0
    }
    if (!(key in seen)) { seen[key] = 1; print; fflush() }
  }'
}

while true; do
  { tail -n0 -F "$SESSION_SPOOL" 2>/dev/null &
    tail -n0 -F "$LEGACY_SPOOL" 2>/dev/null &
    wait; } | dedupe
  sleep 1
done
