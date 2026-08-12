#!/usr/bin/env bash
# agent-talk contact-request monitor (a Claude Code plugin monitor command).
#
# Pushes THIS session's user's incoming CONTACT REQUESTS into the session: a
# peer who was handed one of this identity's invite codes presented it, retalk
# accepted it, and the peer is now a saved contact. The agent should tell the
# user "X just registered using your invite" without being asked.
#
# It is a second monitor rather than a filter on the inbox monitor because the
# two streams are different things. A contact request is a registration event,
# not a conversation turn: it must not be rendered as a chat bubble, it arrives
# only while an invite code is outstanding, and it can be watched by a session
# that is not following any peer's mail yet. Keeping the spools apart also
# keeps decrypted message text out of a file whose whole purpose is onboarding.
#
# It resolves the user from the session->user map that `init` writes
# ($HOME/.agent-talk/by-session/<session-id>), then tails that session's
# request spool, `<user>/sessions/<session-id>.requests.ndjson`, which the
# spool writer fills when run with `--stream requests`.
#
# $1 is ${CLAUDE_SESSION_ID}; if it did not substitute or is empty, it idles
# (push off — the request list can still be read on demand). Diagnostics to
# stderr; only request lines go to stdout.
set -uo pipefail
sid="${1:-}"
case "$sid" in ""|*'${'*) exec tail -f /dev/null;; esac      # no session id -> no push
sid="$(printf '%s' "$sid" | tr -c 'A-Za-z0-9._-' '_')"
map="$HOME/.agent-talk/by-session/$sid"
while [ ! -f "$map" ]; do sleep 2; done                      # init writes it after we start
udir="$(cat "$map")"
REQUEST_SPOOL="$udir/sessions/$sid.requests.ndjson"
mkdir -p "$udir/sessions" 2>/dev/null || true
: >> "$REQUEST_SPOOL" 2>/dev/null || true

# Emit each request once, keyed on its id (falling back to the whole line for a
# record without one). A retried registration repeats the same id, so the user
# hears about a peer once. fflush keeps the monitor line-live.
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
  tail -n0 -F "$REQUEST_SPOOL" 2>/dev/null | dedupe
  sleep 1
done
