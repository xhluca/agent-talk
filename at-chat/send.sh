#!/usr/bin/env bash
# Send a retalk message as the configured identity and log it so it shows in
# the chat pane. Identity/relay come from config.sh.
# Usage: ./send.sh <peer> <message text...>
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.sh"

peer="${1:?usage: send.sh <peer> <text>}"
shift
text="$*"
[ -n "$text" ] || { echo "empty message" >&2; exit 2; }

# 1) send (fails loudly if the peer is unreachable / unknown)
retalk send --peer "$peer" --dir "$AT_IDDIR" "$text"

# 2) log the outgoing message for the chat pane (only after a successful send)
python3 - "$AT_SENT" "$AT_ID" "$AT_NAME" "$peer" "$text" <<'PY'
import json, sys, datetime
sent, me, name, peer, text = sys.argv[1:6]
rec = {
    "id": "out-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"),
    "from": me, "name": name, "to": peer, "text": text,
    "ts": datetime.datetime.now().isoformat(timespec="seconds"),
}
with open(sent, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
echo "logged to chat pane" >&2
