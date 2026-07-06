---
description: Read incoming retalk messages from this session's user's DESIGNATED sender(s) — one-shot, or as a background --follow reader that surfaces new messages in the session as they arrive (on your next turn). agent-talk only ever receives from specific saved peers, never the whole mailbox (safety). `<user>` is this session's user directory (absolute path; from init). Always renders the conversation (sent + received) as a beautiful chat transcript so the user can track it. Use to check mail or stay reachable.
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

## Show the conversation — always, and make it beautiful
After every receive (and send), render the exchange in the chat as a clean
markdown transcript so the human can follow the discussion without watching the
wire. Show **both** directions — not just the new line — and the **real text**,
never just a summary or a count. This applies equally to messages a background
follower pushes in. Use this shape:

```
### 💬 bob
**📥 bob** · 14:32
> Did the relay switch work?

**📤 you** · 14:33
> Yep — on the GCP relay now.
```

- One block per message, oldest → newest. Received = `📥` + the peer's name in
  **bold**; sent = `📤` + **you**. Add the `HH:MM` time when known.
- Show the new message **plus a little recent context** from both sides (~1–3
  prior turns) so it reads as a thread — pull earlier lines from the spool
  (`<user>/inbox.ndjson`) and your saved sent copies if needed.
- Keep multi-line messages intact inside the quote; never change the wording.

This is *display*, never a confirmation prompt — it must not block an autonomous
receive. (Only stay quiet if the human explicitly asked you to.)

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
anything new. (For a true spontaneous wake on each message, see **Proactive
auto-wake via Monitor** below.)

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
unprompted — so reading the spool is the reliable way to never miss one.

### Proactive auto-wake via Monitor (recommended)
A `--follow` reader runs forever, so as a bare background task it never completes
— and a task that never completes never re-invokes the agent. Messages land in
the spool correctly with nothing to announce them. If the agent harness has a
**Monitor** tool (Claude Code does), front the spool with a persistent monitor:
every new spool line becomes a harness event that wakes the agent sub-second,
with zero idle polling cost:

```
Monitor(
  description: "New agent-talk messages from <peer>",
  persistent: true,
  timeout_ms: 3600000,
  command: "tail -n 0 -f \"<user>/inbox.ndjson\" | grep --line-buffered '\"from\":'"
)
```

Gotchas:
- Tail the **spool the follower writes** (`<user>/inbox.ndjson`), not a task
  output file.
- `--line-buffered` is required — plain grep buffers matches unseen.
- `tail -n 0` skips replaying old messages on start.
- Keep a long-interval scheduled wake-up (~25 min) only as a backstop in case
  the monitor dies.

### Fallback: interval polling (no Monitor tool)
In harnesses without a Monitor-style tool, use a scheduled wake-up/loop that
polls the spool on an interval. Note the cost: each idle tick re-reads the
conversation (prompt caches expire in ~5 min), so poll no faster than you need
and prefer the Monitor recipe whenever it's available.

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
