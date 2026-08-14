#!/usr/bin/env bash
# agent-talk message follower: supervise one background `retalk receive
# --follow` for a user and feed its records to the per-session spools.
#
#   follow.sh start  <user-dir> <peer> [<peer2> ...] [options]
#   follow.sh stop   <user-dir>
#   follow.sh status <user-dir>
#
# Options for `start`:
#   --passphrase-path PATH   unlock an encrypted identity by naming the file
#                            that holds the passphrase (retalk 0.3.0+).
#                            The passphrase is never read here; retalk opens
#                            the file itself. On older retalk, leave this off
#                            and export RETALK_PASSPHRASE before calling.
#   --interval N             seconds between polls (default 60; use ~5 for a
#                            rapid live exchange)
#   --wake-codex             also nudge an idle Codex session awake on each
#                            delivered message (opt-in; see spool-writer.py)
#   --no-legacy              stop writing the older per-identity
#                            `<user>/inbox.ndjson` alongside the session spools
#
# Why a script instead of the shell block the skills used to inline: that block
# was a single long `nohup env ... bash -c '...'` string. A compound command
# like that cannot be matched by a prefix allowlist rule, so every start had to
# be approved by hand, and the encrypted case had to read the passphrase into
# the environment first. One command with the secret named by path fixes both.
#
# Layout is unchanged, so a follower started by an older version of the skills
# is still found and stopped by this one: the supervisor's pid goes in
# `<user>/follow.<peer>[+<peer2>...].pid`, retalk's stderr in
# `<user>/follow.err`, and records land in the spools the writer manages.
set -o pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRITER="$HERE/spool-writer.py"

usage() {
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
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
peers=(); pp=""; interval=60; writer_opts=()
while [ $# -gt 0 ]; do
  case "$1" in
    --passphrase-path|--passphrase-file) pp="${2:-}"; shift 2 ;;
    --interval)                          interval="${2:-}"; shift 2 ;;
    --wake-codex|--no-legacy)            writer_opts+=("$1"); shift ;;
    --*) echo "follow.sh: unknown option $1" >&2; exit 2 ;;
    *)   peers+=("$1"); shift ;;
  esac
done

label=""
for p in "${peers[@]}"; do label="${label:+$label+}$p"; done
PID="$UD/follow.$label.pid"

case "$action" in

start)
  if [ ${#peers[@]} -eq 0 ]; then
    echo "follow.sh: name at least one peer to follow" >&2; exit 2
  fi
  mkdir -p "$UD"
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "already following ${peers[*]} (pid $(cat "$PID"))"; exit 0
  fi
  nohup "${BASH_SOURCE[0]}" __run "$UD" "${ORIG[@]}" >/dev/null 2>&1 &
  echo $! > "$PID"
  echo "following ${peers[*]} (pid $(cat "$PID"))"
  ;;

__run)
  # The supervised loop. retalk exits on a relay hiccup or a rotated session;
  # restarting it after a short pause is what keeps a session-long listener
  # alive. Records go to the writer, which fans them out to every session
  # registered to this user.
  export RETALK_SAVE_MESSAGE=1
  peer_args=()
  for p in "${peers[@]}"; do peer_args+=(--peer "$p"); done
  pp_args=()
  [ -n "$pp" ] && pp_args=(--passphrase-path "$pp")
  while true; do
    retalk receive "${peer_args[@]}" --follow --interval "$interval" --quiet \
        --dir "$UD/identity" "${pp_args[@]}" 2>> "$UD/follow.err" \
      | python3 "$WRITER" --user "$UD" "${writer_opts[@]}" 2>> "$UD/follow.err"
    sleep 2
  done
  ;;

stop)
  for f in "$UD"/follow.*.pid; do
    [ -e "$f" ] || continue
    kill "$(cat "$f")" 2>/dev/null
    rm -f "$f"
  done
  pkill -f "retalk receive .*--dir $UD/identity" 2>/dev/null
  echo "stopped"
  ;;

status)
  running=0
  for f in "$UD"/follow.*.pid; do
    [ -e "$f" ] || continue
    who="$(basename "$f" .pid)"; who="${who#follow.}"
    if kill -0 "$(cat "$f")" 2>/dev/null; then
      echo "following: $who (pid $(cat "$f"))"; running=1
    fi
  done
  [ "$running" = 1 ] || echo "not following"
  echo "--- recent messages ---"
  # Claude Code substitutes ${CLAUDE_SESSION_ID} into a monitor's command line
  # but does not export it into the Bash tool's environment, so reading the
  # variable here yields nothing. Take the id from whatever is available, else
  # the most recently written session spool, else the legacy inbox.
  sid="${CLAUDE_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-}}"
  spool=""
  [ -n "$sid" ] && [ -f "$UD/sessions/$sid.ndjson" ] \
    && spool="$UD/sessions/$sid.ndjson"
  if [ -z "$spool" ]; then
    spool="$(ls -1t "$UD"/sessions/*.ndjson 2>/dev/null \
             | grep -v '\.requests\.ndjson$' | head -n 1)"
  fi
  if [ -n "$spool" ] && [ -s "$spool" ]; then
    tail -n 20 "$spool"
  else
    tail -n 20 "$UD/inbox.ndjson" 2>/dev/null || echo "(none yet)"
  fi
  ;;

esac
