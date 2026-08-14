#!/usr/bin/env bash
# agent-talk invite watcher: supervise one background `retalk invite watch
# --follow` for a user and feed its records to the per-session request spools.
#
#   invite-watch.sh start  <user-dir> [options]
#   invite-watch.sh stop   <user-dir>
#   invite-watch.sh status <user-dir>
#
# Options for `start`:
#   --passphrase-path PATH   unlock an encrypted identity by naming the file
#                            that holds the passphrase (retalk 0.3.0+).
#                            The watcher decrypts, so an encrypted identity
#                            needs it. The passphrase is never read here;
#                            retalk opens the file itself.
#   --interval N             seconds between polls (default 10, a calm rate
#                            while a code is outstanding)
#
# Run it while an invite code is outstanding, and stop it once every code has
# been redeemed or revoked. Records land in
# `<user>/sessions/<session-id>.requests.ndjson`, separate from message mail,
# where the plugin's `retalk-requests` monitor picks them up.
#
# Same reasoning as follow.sh: the skills used to inline this as one long
# `nohup env ... bash -c '...'` string, which no prefix allowlist rule can
# match and which had to read the passphrase into the environment first.
set -o pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRITER="$HERE/spool-writer.py"

usage() {
  sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
}

action="${1:-}"; shift 2>/dev/null
case "$action" in
  start|stop|status|__run) ;;
  *) usage; exit 2 ;;
esac

UD="${1:-}"; shift 2>/dev/null
case "$UD" in "") usage; exit 2 ;; esac
UD="${UD%/}"

ORIG=("$@")
pp=""; interval=10
while [ $# -gt 0 ]; do
  case "$1" in
    --passphrase-path|--passphrase-file) pp="${2:-}"; shift 2 ;;
    --interval)                          interval="${2:-}"; shift 2 ;;
    *) echo "invite-watch.sh: unknown argument $1" >&2; exit 2 ;;
  esac
done

PID="$UD/invite-watch.pid"

case "$action" in

start)
  mkdir -p "$UD"
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "already watching (pid $(cat "$PID"))"; exit 0
  fi
  nohup "${BASH_SOURCE[0]}" __run "$UD" "${ORIG[@]}" >/dev/null 2>&1 &
  echo $! > "$PID"
  echo "watching for registrations (pid $(cat "$PID"))"
  ;;

__run)
  pp_args=()
  [ -n "$pp" ] && pp_args=(--passphrase-path "$pp")
  while true; do
    retalk invite watch --follow --interval "$interval" --quiet \
        --dir "$UD/identity" "${pp_args[@]}" 2>> "$UD/invite-watch.err" \
      | python3 "$WRITER" --user "$UD" --stream requests 2>> "$UD/invite-watch.err"
    sleep 2
  done
  ;;

stop)
  [ -f "$PID" ] && kill "$(cat "$PID")" 2>/dev/null
  pkill -f "retalk invite watch .*--dir $UD/identity" 2>/dev/null
  rm -f "$PID"
  echo "stopped watching"
  ;;

status)
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "watching (pid $(cat "$PID"))"
  else
    echo "not watching"
  fi
  echo "--- recent registrations ---"
  # Which spool to read. Claude Code substitutes ${CLAUDE_SESSION_ID} into a
  # monitor's command line, but it does NOT export it into the environment of
  # the Bash tool, so reading the variable here yields nothing and the status
  # used to report "(none yet)" while accepted registrations sat on disk. Take
  # the id from whatever is actually available, and otherwise read the most
  # recently written request spool, which is this user's live session in every
  # case that matters.
  sid="${CLAUDE_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-}}"
  spool=""
  [ -n "$sid" ] && [ -f "$UD/sessions/$sid.requests.ndjson" ] \
    && spool="$UD/sessions/$sid.requests.ndjson"
  if [ -z "$spool" ]; then
    spool="$(ls -1t "$UD"/sessions/*.requests.ndjson 2>/dev/null | head -n 1)"
  fi
  if [ -n "$spool" ] && [ -s "$spool" ]; then
    tail -n 20 "$spool"
  else
    echo "(none yet)"
  fi
  ;;

esac
