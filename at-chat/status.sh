#!/usr/bin/env bash
# Render a visual status overview of the agent-talk workspace from LIVE state.
# Called automatically at the end of start.sh; safe to run anytime on its own.
# Identity/relay/peer come from config.sh.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.sh"

PANE_TITLE="${AT_USER}·chat"    # tmux title of the chat pane
SUP_PAT="$AT_SUP_PAT"           # this identity's follow-reader (scoped, from config)

# --- relay reachability ---
code=$(curl -sS -m 6 -o /dev/null -w '%{http_code}' "$AT_RELAY/" 2>/dev/null || echo "down")
if [ "$code" = "down" ]; then relay="● down"; else relay="● reachable ($code)"; fi

# --- chat pane ---
if [ -n "${TMUX:-}" ]; then
  pane=$(tmux list-panes -a -F '#{pane_id} #{pane_title}' 2>/dev/null \
    | awk -v t="$PANE_TITLE" '$2==t{print $1; exit}')
  if [ -n "$pane" ]; then pane_s="● open  ($pane)"; else pane_s="○ closed"; fi
else
  pane_s="○ no tmux"
fi

# --- follow-reader(s) ---  (bash 3.2 friendly: no mapfile)
SUPS=$(pgrep -f "$SUP_PAT" 2>/dev/null || true)
set -- $SUPS
nsup=$#
if [ "$nsup" -eq 0 ]; then
  reader_s="○ none running"
elif [ "$nsup" -eq 1 ]; then
  reader_s="● running (PID $1, no dups)"
else
  reader_s="⚠ ${nsup} running (DUPLICATES — run ./start.sh to reap)"
fi

# peers we follow = --peer value(s) on the supervisor command lines. start.sh
# embeds the real peer (single-quoted) into argv, so read it straight from ps.
peers=$(for p in $SUPS; do
  ps -o command= -p "$p" 2>/dev/null
done | grep -oE -- "--peer ['\"]?[A-Za-z0-9_.-]+" | sed -E "s/--peer ['\"]?//" | sort -u)
[ -n "$peers" ] || peers="(none)"

# --- spools ---
sl() { [ -f "$1" ] && wc -l < "$1" | tr -d ' ' || echo "—"; }
in_n=$(sl "$AT_INBOX"); out_n=$(sl "$AT_SENT"); seen_n=$(sl "$AT_SEEN")

# --- header ---  (box auto-sizes to the widest line, +2 for padding)
HDR="agent-talk · ${AT_USER}  —  session status"
L_ID="  Identity   ${AT_USER}   ${AT_ID}  (no passphrase)"
L_RY="  Relay      ${AT_RELAY}   ${relay}"
L_PN="  Chat pane  ${pane_s}"
L_RD="  Reader     ${reader_s}"

W=0
for s in "$HDR" "$L_ID" "$L_RY" "$L_PN" "$L_RD"; do
  (( ${#s} > W )) && W=${#s}
done
W=$(( W + 2 ))

hbar() { local l="$1" r="$2" i s=""; for ((i=0;i<W;i++)); do s+="═"; done; printf '%s%s%s\n' "$l" "$s" "$r"; }
row()  { local s="$1" pad=$(( W - ${#1} )); (( pad<0 )) && pad=0; printf '║%s%*s║\n' "$s" "$pad" ""; }
rowc() { local s="$1" t=$(( W - ${#1} )) l r; (( t<0 )) && t=0; l=$(( t/2 )); r=$(( t-l ))
         printf '║%*s%s%*s║\n' "$l" "" "$s" "$r" ""; }

printf '\n'
hbar '╔' '╗'
rowc "$HDR"
hbar '╠' '╣'
row  "$L_ID"
row  "$L_RY"
row  "$L_PN"
row  "$L_RD"
hbar '╚' '╝'

# --- contacts table (live retalk) ---
# Capture first (so a retalk failure can't abort the script via pipefail),
# then feed via stdin to a -c program (stdin stays free for the data).
contacts_json=$(retalk contacts --json --dir "$AT_IDDIR" 2>/dev/null || true)
printf '%s\n' "$contacts_json" | python3 -c '
import sys, json
rows = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    rows.append(d) if isinstance(d, dict) else rows.extend(d)
print("\n  CONTACTS (live retalk - verified == OK)")
print("  +--------------+----------------------------------+----------+")
print("  | Name         | Fingerprint                      | Verified |")
print("  +--------------+----------------------------------+----------+")
nver = 0
for r in rows:
    name = (r.get("name") or "?")[:12].ljust(12)
    fpr = (r.get("fingerprint") or "?")[:32].ljust(32)
    ver = "Yes" if r.get("verified") else "No "
    nver += 1 if r.get("verified") else 0
    print(f"  | {name} | {fpr} |   {ver}    |")
print("  +--------------+----------------------------------+----------+")
print(f"                                  {len(rows)} contact(s) - {nver} verified")
'

# --- following + spools ---
cat <<EOF

  FOLLOWING (live --follow readers → inbox spool)
    peers: ${peers}

  SPOOLS (persist between sessions)
    inbox.ndjson  ${in_n}  incoming
    sent.ndjson   ${out_n}  outgoing
    seen.ndjson   ${seen_n}  first-seen timestamps
EOF
