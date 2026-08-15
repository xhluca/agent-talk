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
pp_args=()
[ -n "$pp" ] && pp_args=(--passphrase-path "$pp")

# `kill -0` succeeds on a zombie, which is what a dead watcher becomes whenever
# nothing reaps it (PID 1 in a container is often not an init). Believing it
# made `status` report a watcher that had been gone for minutes, and made
# `start` refuse to restart one. Check the process state, not just its
# existence.
alive() {
  pid="${1:-}"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  if [ -r "/proc/$pid/status" ]; then
    grep -qi '^State:[[:space:]]*Z' "/proc/$pid/status" && return 1
    return 0
  fi
  case "$(ps -o stat= -p "$pid" 2>/dev/null)" in *Z*) return 1 ;; esac
  return 0
}

# A registration saves the contact, but nothing yet delivers their mail.
# `receive-from` names the follower's scope and was chosen before this peer
# existed, and a running follower's peer list is fixed when it starts. So the
# first thing a brand-new peer sends, which is the entire point of an invite
# code, would sit on the relay until someone ran `receive` naming them. Widen
# the scope here, where the acceptance is already known, rather than leaving it
# to the agent noticing the spool record: on a host with no request monitor it
# never sees one.
cover_contact() {
  line="$1"
  name="$(printf '%s' "$line" | python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get("name") or "")
except Exception:
    print("")' 2>/dev/null)"
  [ -n "$name" ] || return 0

  rf=""
  [ -r "$UD/receive-from" ] && rf="$(tr -d '[:space:]' < "$UD/receive-from")"
  case "$rf" in
    "")                    printf '%s\n' "$name" > "$UD/receive-from"; rf="$name" ;;
    "$name"|'*contacts*')  ;;   # already covers this peer
    *)                     printf '%s\n' '*contacts*' > "$UD/receive-from"
                           rf='*contacts*' ;;
  esac

  # Only `auto` keeps a live follower. `manual` is a deliberate choice to read
  # on demand, so widening the recorded scope is all that is wanted there.
  mode=""
  [ -r "$UD/check-mode" ] && mode="$(tr -d '[:space:]' < "$UD/check-mode")"
  [ "$mode" = auto ] || return 0

  new_peers=()
  if [ "$rf" = '*contacts*' ]; then
    while IFS= read -r p; do
      [ -n "$p" ] && new_peers+=("$p")
    done < <(retalk contacts --json --dir "$UD/identity" "${pp_args[@]}" 2>/dev/null \
             | python3 -c 'import json,sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    n = d.get("name") or d.get("fingerprint")
    if n:
        print(n)' 2>/dev/null)
  else
    new_peers=("$rf")
  fi
  [ ${#new_peers[@]} -gt 0 ] || new_peers=("$name")

  opts=()
  if [ -r "$UD/follow.opts" ]; then
    while IFS= read -r o; do [ -n "$o" ] && opts+=("$o"); done < "$UD/follow.opts"
  elif [ -n "$pp" ]; then
    opts=(--passphrase-path "$pp")
  fi

  "$HERE/follow.sh" stop "$UD" >/dev/null 2>&1
  "$HERE/follow.sh" start "$UD" "${new_peers[@]}" "${opts[@]}" \
    >> "$UD/invite-watch.err" 2>&1
}

case "$action" in

start)
  mkdir -p "$UD"
  if [ -f "$PID" ] && alive "$(cat "$PID" 2>/dev/null)"; then
    echo "already watching (pid $(cat "$PID"))"; exit 0
  fi
  rm -f "$PID"
  # `setsid` puts the watcher in its own session, so it outlives the shell that
  # started it. Without it, a watcher started inside a headless `codex exec`
  # turn is killed with that turn's process group the moment the turn ends,
  # which is exactly when the invite code has just gone out.
  if command -v setsid >/dev/null 2>&1; then
    setsid nohup "${BASH_SOURCE[0]}" __run "$UD" "${ORIG[@]}" \
      >/dev/null 2>&1 </dev/null &
  else
    nohup "${BASH_SOURCE[0]}" __run "$UD" "${ORIG[@]}" \
      >/dev/null 2>&1 </dev/null &
  fi
  # `__run` records its own pid: `setsid` forks when it is already a process
  # group leader, so `$!` here is not reliably the watcher's pid.
  n=0
  while [ ! -s "$PID" ] && [ "$n" -lt 50 ]; do sleep 0.1; n=$((n + 1)); done
  if [ -s "$PID" ]; then
    echo "watching for registrations (pid $(cat "$PID"))"
  else
    echo "invite-watch.sh: the watcher did not start; see $UD/invite-watch.err" >&2
    exit 1
  fi
  ;;

__run)
  echo $$ > "$PID"
  while true; do
    # The middle stage passes every record through untouched and, on an
    # acceptance, widens delivery to cover the peer who just registered. It
    # runs in the background so the record still reaches the spool at once:
    # restarting the follower takes about a second, and the registration
    # should not wait behind it.
    retalk invite watch --follow --interval "$interval" --quiet \
        --dir "$UD/identity" "${pp_args[@]}" 2>> "$UD/invite-watch.err" \
      | while IFS= read -r line; do
          printf '%s\n' "$line"
          case "$line" in
            *'"contact_accepted"'*) cover_contact "$line" & ;;
          esac
        done \
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
  if [ -f "$PID" ] && alive "$(cat "$PID" 2>/dev/null)"; then
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
  # Last resort: the per-identity file the writer uses when no session is
  # registered, which is every host other than Claude Code.
  if [ -z "$spool" ] || [ ! -s "$spool" ]; then
    [ -s "$UD/requests.ndjson" ] && spool="$UD/requests.ndjson"
  fi
  if [ -n "$spool" ] && [ -s "$spool" ]; then
    tail -n 20 "$spool"
  else
    echo "(none yet)"
  fi
  ;;

esac
