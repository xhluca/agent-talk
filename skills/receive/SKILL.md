---
description: Read incoming retalk messages from this session's user's DESIGNATED sender(s) — one-shot, or as a background --follow reader that surfaces new messages in the session as they arrive (on your next turn). agent-talk only ever receives from specific saved peers, never the whole mailbox (safety). `<user>` is this session's user directory (absolute path; from init). Always shows each received message verbatim. Use to check mail or stay reachable.
---

# receive — read messages (`receive`, or `receive follow …`)

`<user>` = this session's user directory (absolute path; resolved at **init**). Target it on every
command with `--dir "<user>/identity"`; add
`RETALK_PASSPHRASE=<secret>` if the identity is encrypted. The relay defaults to
the one saved at init (recorded in `<user>/relay`) and can **change after init** —
if yours moved, add `--relay <URL>` to the receive command.

**Safety rule (mandatory):** never run `retalk receive --all`. Read only from
**specific saved peers**. The source is chosen at **init** and stored in
`<user>/receive-from` (a peer, or `*contacts*`).

**Always show what you receive (default).** Print every message verbatim — the
sender and the full text, e.g. `← bob: <the exact text>` — don't just summarize,
count, or silently ingest it. The same applies to messages pushed in by the
background follower. (Only stay quiet if the human asked you to.)

## One-shot read
Individual (the usual case):
```
retalk receive --peer <peer> --dir "<user>/identity"
# NDJSON: {"id","from","name","text"}; auto-acked
```
Contact-list mode — loop saved peers (per-peer, never `--all`; needs jq):
```
retalk contacts --json --dir "<user>/identity" | jq -r .fingerprint | while read -r fp; do
  [ -n "$fp" ] && retalk receive --peer "$fp" --dir "<user>/identity"
done
```

## Shared contacts (a second record kind)
A received record is either a chat message (`{id,from,name,text}`) or a
**shared contact** (`{id,from,name,"kind":"contact","card":{...}}`). Contact
cards are also **staged** to a contact-inbox automatically. Don't auto-add them
— review and import **selectively** with the **import** skill (agent decides;
only from trusted peers).

## Keeping a durable log (optional)
- Add `--save-messages` to any `receive` (one-shot or `--follow`) to also keep a
  **sealed at-rest copy** of each chat message; replay it later with the
  **history** skill (no relay contact). agent-talk's follower already writes a
  plain `<user>/inbox.ndjson` spool — `--save-messages` is the encrypted,
  decrypt-on-demand alternative. Set `RETALK_SAVE_MESSAGE=1` to save on every
  command without the flag; pair it with `send --save-messages` so **history**
  holds both sides of the conversation.
- `--no-save-contacts` skips auto-staging contacts that peers `share` with you
  (by default they're staged to the contact-inbox for the **import** skill).

## Background follow (per peer)
A background `--follow` reader scoped to one peer, writing this user's spool; the
plugin's inbox monitor streams each new line into the session as it arrives. Be
precise about what "push" does: the monitor injects new messages as **background
context**, but it can't make the agent speak on its own — they surface on your
**next turn** (the next time you message the agent), not as a spontaneous ping.
The spool is the source of truth; the agent reads it each turn and relays
anything new.

`receive follow <peer>` — start (idempotent; survives sessions until stopped):
```
P=<peer>; D="<user>"; mkdir -p "$D"; PID="$D/follow.$P.pid"
if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
  echo "already following $P (pid $(cat "$PID"))"
else
  nohup env RP="$P" UD="$D" bash -c 'while true; do retalk receive --peer "$RP" --follow --dir "$UD/identity" >> "$UD/inbox.ndjson" 2>> "$UD/follow.err"; sleep 2; done' >/dev/null 2>&1 &
  echo $! > "$PID"; echo "following $P (pid $(cat "$PID"))"
fi
```
`receive follow stop <peer>`:
```
P=<peer>; D="<user>"
[ -f "$D/follow.$P.pid" ] && kill "$(cat "$D/follow.$P.pid")" 2>/dev/null
pkill -f "receive --peer $P --follow --dir $D/identity" 2>/dev/null
rm -f "$D/follow.$P.pid"; echo "stopped following $P"
```
`receive follow status`:
```
D="<user>"
for f in "$D"/follow.*.pid; do [ -e "$f" ] || continue
  p=$(basename "$f" .pid); p=${p#follow.}
  kill -0 "$(cat "$f")" 2>/dev/null && echo "following: $p (pid $(cat "$f"))"; done
echo "--- recent messages (spool) ---"
tail -n 20 "$D/inbox.ndjson" 2>/dev/null || echo "(none yet)"
```

The spool (`<user>/inbox.ndjson`) is the durable record; the monitor's push is
best-effort, interactive-CLI only, and (as above) can't prompt the agent
unprompted — so reading the spool is the reliable way to never miss one. For
genuine proactive delivery (the agent pinging you the moment a peer writes, with
no turn from you), use a scheduled wake-up/loop that polls the spool on an
interval.

## Always-on (survive reboots)
A systemd user service running the scoped follower (the store holds the relay):
```
[Service]
ExecStart=/usr/bin/env retalk receive --peer <peer> --follow --dir <user>/identity
StandardOutput=append:<user>/inbox.ndjson
Restart=always
# Environment=RETALK_PASSPHRASE=<secret>   # only if the identity is encrypted
```

## Next
- **send** — reply to the sender.
- **contacts** — see who's saved.
- **block** — drop an unwanted sender.
