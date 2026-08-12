---
name: receive
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

**Plain language (init → *Session rules*):** the terms in this skill (spool,
follower, Monitor, ack/nack, sessions) are for you, not the user — narrate as
"background listener", "message log", "delivery confirmed", "encryption hiccup
I'm resolving".

**Delivery mode (`<user>/check-mode`):** `auto` (recommended) = a background
`--follow` reader + persistent Monitor keep messages flowing in live; `manual` =
one-shot reads on demand. Honor the recorded mode. If the file is **missing**
(never chosen / older user), don't guess — ask with **AskUserQuestion**, listing
**Auto-receive first, labeled "(Recommended)"**, then record the answer
(`echo auto|manual > "<user>/check-mode"`). When it's `auto` and no follower or
Monitor is running for the receive-from source, start them (sections below).

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

## Group-room messages — render the room, not a 1:1
A received message may carry two extra fields, `group` (the room's name) and
`group_id` (its stable 32-hex id). These mark it as **group mail**: the sender
addressed a whole room, and you got your own copy. Keep the 1:1 rendering above
for messages without them; when they're present, render a **group-room
transcript** instead:

```
### 💬 team
**📥 bob** · 14:30
> standup in 5

**📥 carol** · 14:31
> on my way

**📤 you** · 14:32
> 2 min
```

- Head the block with the **room name** (`💬 <group>`), then each message
  oldest → newest, **attributed to its sender** by name — several different
  people, not one peer. `📥` + the sender's **bold** name for incoming, `📤`
  **you** for your own group sends.
- **Distinguish senders consistently.** Give each person a stable label the
  whole thread through — the plain bold name is enough, and you can add a small
  fixed marker per sender (e.g. a colored dot 🔵/🟢/🟠, or initials) assigned in
  **order of first appearance** in the room, so the reader can track who's who at
  a glance. Reuse the same marker for the same sender every time.
- **Thread by `group_id`, not by name.** Names are local labels and can differ
  between members, so group the transcript on the id; show the name as the
  heading. Different rooms → different transcripts.
- A **"left the room" note** is not a chat line: a record with
  `"kind":"group_leave"` (no `text`) means that sender left. Render it as a quiet
  system line inside the room, not a message bubble:

  > _carol left the room_

  retalk drops them from the room's roster automatically, so you'll stop sending
  them copies — nothing for you to do.

## One-shot read
Individual (the usual case):
```
RETALK_SAVE_MESSAGE=1 retalk receive --peer <peer> --dir "<user>/identity"
# NDJSON: {"id","from","name","text"}; auto-acked
```
Contact-list mode — loop saved peers (per-peer, never `--all`; needs jq):
```
retalk contacts --json --dir "<user>/identity" | jq -r .fingerprint | while read -r fp; do
  [ -n "$fp" ] && RETALK_SAVE_MESSAGE=1 retalk receive --peer "$fp" --dir "<user>/identity"
done
```

## Other record kinds (not chat)
A received record is usually a chat message (`{id,from,name,text}`, optionally
with `group`/`group_id`), but the stream also carries control records. Tell them
apart by the fields, and don't render a control record as a chat bubble:
- **Shared contact** — `{id,from,name,"kind":"contact","card":{...}}`. Contact
  cards are also **staged** to a contact-inbox automatically. Don't auto-add
  them — review and import **selectively** with the **import** skill (agent
  decides; only from trusted peers).
- **Group leave** — `{id,from,name,"kind":"group_leave","group_id"}` (no
  `text`). The sender left that room; retalk drops them from its roster for you.
  Show it as the quiet "left the room" line in the group transcript above.

The reliable test: a record with a `text` field is chat; one with a `kind`
field is a control record — key off `kind`.

**Contact requests do not come through here.** A peer registering with one of
your invite codes sends their request from an address you have not saved yet, and
`receive` only ever reads designated senders. Those requests are handled by
`retalk invite watch`, land in a separate per-session spool
(`<user>/sessions/<session-id>.requests.ndjson`), and are pushed by the plugin's
second monitor, `retalk-requests`. See the **id** skill, *Invite codes* (retalk
0.3.0-rc.1 or newer). Once a peer has registered, they are an ordinary saved
contact and their mail arrives here like anyone else's.

## Keeping a durable log (on by default)
- agent-talk sets `RETALK_SAVE_MESSAGE=1` on every `receive` (shown above and in
  the follower below), so each chat message also gets a **sealed at-rest copy**
  you can replay later with the **history** skill (no relay contact). This runs
  alongside the plain `<user>/inbox.ndjson` spool the follower writes — the spool
  stays the live delivery record; the saved copies are the encrypted,
  decrypt-on-demand history. **send** saves the same way, so **history** holds
  both sides of the conversation.
- The env var is version-agnostic; use it (not a `--save`/`--save-messages`
  flag) so the plugin works on both the installed retalk and newer releases.
- `--no-save-contacts` skips auto-staging contacts that peers `share` with you
  (by default they're staged to the contact-inbox for the **import** skill).

## Background follow
One background `--follow` reader covers the receive-from source — one peer or
several in a single process (repeat `--peer`; retalk 0.2.0+), each still its own
scoped read. It polls calmly (`--interval 60`), writes only NDJSON records
(`--quiet`), and pipes them through the plugin's spool writer, which stamps an
arrival time and copies each record to **every session registered to this user**
(`<user>/sessions/<session-id>.ndjson`). Two sessions sharing one identity each
get their own copy and their own read position instead of racing for the same
lines, and the decrypted text lives only as long as the session does. retalk's
saved history stays the durable record. The plugin's inbox monitor streams each
new line into the session as it arrives. Be
precise about what "push" does: the monitor injects new messages as **background
context**, but it can't make the agent speak on its own — they surface on your
**next turn** (the next time you message the agent), not as a spontaneous ping.
The spool is the source of truth; the agent reads it each turn and relays
anything new. (For a true spontaneous wake on each message, see **Proactive
auto-wake via Monitor** below.)

`receive follow <peer> [<peer2> …]` — start (idempotent; survives sessions
until stopped):
```
D="<user>"; PEERS="<peer> [<peer2> …]"; LBL=${PEERS// /+}
mkdir -p "$D"; PID="$D/follow.$LBL.pid"
if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
  echo "already following $PEERS (pid $(cat "$PID"))"
else
  nohup env RP="$PEERS" UD="$D" W="<plugin>/bin/spool-writer.py" RETALK_SAVE_MESSAGE=1 bash -c 'A=""; for p in $RP; do A="$A --peer $p"; done; while true; do retalk receive $A --follow --interval 60 --quiet --dir "$UD/identity" 2>> "$UD/follow.err" | python3 "$W" --user "$UD" 2>> "$UD/follow.err"; sleep 2; done' >/dev/null 2>&1 &
  echo $! > "$PID"; echo "following $PEERS (pid $(cat "$PID"))"
fi
```
- `<plugin>` is this plugin's root (`${CLAUDE_PLUGIN_ROOT}` under Claude Code).
  The writer keeps writing the older `<user>/inbox.ndjson` as well, so a consumer
  still pointed at that path keeps working; add `--no-legacy` once nothing reads
  it.
- **Codex + `codex-with-daemon` only:** if the user starts their Codex sessions
  through the `codex-with-daemon` launcher (so idle sessions can be woken, see
  init step 4d), append `--wake-codex` to the spool-writer command above. Each
  delivered message then also nudges the idle session awake, best-effort and
  silent when no daemon is reachable. Do not add the flag otherwise; hooks
  alone deliver at the next prompt or end of turn, and waking is the user's
  opt-in.
- For a rapid live exchange, restart with a smaller `--interval` (e.g. 5); 60
  is the calm default for all-session listening.
- retalk older than 0.2.0 has none of these flags: drop `--interval`/`--quiet`
  and run one `receive --peer X --follow` process per peer (the init skill's
  install-or-upgrade step normally makes this moot).

`receive follow stop`:
```
D="<user>"
for f in "$D"/follow.*.pid; do [ -e "$f" ] || continue
  kill "$(cat "$f")" 2>/dev/null; rm -f "$f"; done
pkill -f "retalk receive .*--dir $D/identity" 2>/dev/null; echo "stopped"
```
`receive follow status`:
```
D="<user>"
for f in "$D"/follow.*.pid; do [ -e "$f" ] || continue
  p=$(basename "$f" .pid); p=${p#follow.}
  kill -0 "$(cat "$f")" 2>/dev/null && echo "following: $p (pid $(cat "$f"))"; done
echo "--- recent messages (this session's spool) ---"
tail -n 20 "$D/sessions/${CLAUDE_SESSION_ID}.ndjson" 2>/dev/null \
  || tail -n 20 "$D/inbox.ndjson" 2>/dev/null || echo "(none yet)"
```

The spool (`<user>/sessions/<session-id>.ndjson`) is this session's record of
what arrived; retalk's saved history (**history** skill) is the durable one that
survives the session. The monitor's push is
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
  command: "tail -n 0 -F \"<user>/sessions/<session-id>.ndjson\" | grep --line-buffered '\"from\":'"
)
```

Gotchas:
- Tail **this session's spool** (`<user>/sessions/<session-id>.ndjson`), not a
  task output file, and not another session's. Use `-F` so the tail survives the
  spool being rotated or swept.
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
ExecStart=/bin/sh -c 'retalk receive --peer <peer> --follow --interval 60 --quiet --dir <user>/identity | python3 <plugin>/bin/spool-writer.py --user <user>'
Restart=always
Environment=RETALK_SAVE_MESSAGE=1
# Environment=RETALK_PASSPHRASE=<secret>   # only if the identity is encrypted
```

## Next
- **send** — reply to the sender (or the whole room with `--group`).
- **contacts** — see who's saved.
- **group** — see or adjust a room's members.
- **block** — drop an unwanted sender.
- **id** — issue an invite code and watch for a new peer to register themselves.
