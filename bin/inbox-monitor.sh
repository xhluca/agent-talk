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
# The session id comes from CLAUDE_CODE_SESSION_ID, which Claude Code exports
# into the monitor's environment. An optional $1 overrides it (tests pass one);
# with neither, it idles
# (push off — pull via the `receive` skill still works). Diagnostics to stderr;
# only message lines go to stdout.
set -uo pipefail
sid="${1:-}"
# Claude Code substitutes ${CLAUDE_PLUGIN_ROOT} into a monitor's command line but
# NOT ${CLAUDE_SESSION_ID}: that literal used to arrive as $1, the guard below
# read it as "no session id", and push was silently off for every session.
# monitors.json no longer passes it. The value Claude Code does export is
# CLAUDE_CODE_SESSION_ID, so that is the primary source, as in bin/follow.sh
# and bin/invite-watch.sh; $1 stays as an explicit override.
case "$sid" in ""|*'${'*) sid="${CLAUDE_CODE_SESSION_ID:-}";; esac
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
