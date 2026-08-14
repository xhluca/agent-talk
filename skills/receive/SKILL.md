---
name: receive
description: Read incoming retalk messages from this session's user's DESIGNATED sender(s) — one-shot, or as a background --follow reader that surfaces new messages in the session as they arrive (on your next turn). agent-talk only ever receives from specific saved peers, never the whole mailbox (safety). `<user>` is this session's user directory (absolute path; from init). Always renders the conversation (sent + received) as a beautiful chat transcript so the user can track it. Use to check mail or stay reachable.
---

# receive — read messages (`receive`, or `receive follow …`)

`<user>` = this session's user directory (absolute path; resolved at **init**). Target it on every
command with `--dir "<user>/identity"`; add
`--passphrase-path "<user>/passphrase"` if the identity is encrypted (retalk
0.3.0+ — one flat command, the secret stays in the file; **init** Session
rule 8 has the older-retalk fallback). The relay defaults to
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
retalk receive --peer <peer> --save --dir "<user>/identity" --passphrase-path "<user>/passphrase"
# NDJSON: {"id","from","name","text"}; auto-acked
```
`--save` keeps the sealed at-rest copy that **history** replays; leave it off and
the message is read once and gone. Keeping it inside the command, rather than the
`RETALK_SAVE_MESSAGE=1` prefix the older skills used, means the whole call is one
`retalk …` command a single `Bash(retalk:*)` rule can allow, and there is no
prefix to drop by accident. The passphrase is named by path and never read into
the command (drop that flag on a `--no-passphrase` identity).
Contact-list mode — loop saved peers (per-peer, never `--all`; needs jq):
```
retalk contacts --json --dir "<user>/identity" | jq -r .fingerprint | while read -r fp; do
  [ -n "$fp" ] && retalk receive --peer "$fp" --save --dir "<user>/identity" --passphrase-path "<user>/passphrase"
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
0.3.0 or newer). Once a peer has registered, they are an ordinary saved
contact and their mail arrives here like anyone else's.

## Keeping a durable log (on by default)
- agent-talk passes `--save` on every `receive` and every `send` (the follower
  below sets `RETALK_SAVE_MESSAGE=1` instead, which is the same switch in the
  form a long-running process wants), so each chat message gets a **sealed
  at-rest copy**
  you can replay later with the **history** skill (no relay contact). This runs
  alongside the plain `<user>/inbox.ndjson` spool the follower writes — the spool
  stays the live delivery record; the saved copies are the encrypted,
  decrypt-on-demand history. **send** saves the same way, so **history** holds
  both sides of the conversation.
- Both forms have existed since retalk 0.0.12 and mean the same thing. Use the
  flag in a command you write out, and the environment variable only where a
  process inherits it (the follower, a systemd unit).
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

The plugin ships the supervisor as a script, so each of these is **one command**
with the paths written out in full — nothing to assemble inline, and nothing
that reads the passphrase:

`receive follow <peer> [<peer2> …]` — start (idempotent; survives sessions
until stopped):
```
<plugin>/bin/follow.sh start "<user>" <peer> [<peer2> …] --passphrase-path "<user>/passphrase"
```
`receive follow stop` / `receive follow status`:
```
<plugin>/bin/follow.sh stop "<user>"
<plugin>/bin/follow.sh status "<user>"
```
- `<plugin>` is this plugin's root (`${CLAUDE_PLUGIN_ROOT}` under Claude Code).
  The script finds the spool writer beside itself, sets `RETALK_SAVE_MESSAGE=1`,
  and restarts `retalk receive` if it dies. It keeps the same pid file
  (`<user>/follow.<peers>.pid`) and stderr log (`<user>/follow.err`) as before,
  so it also finds and stops a follower an older version of this skill started.
- **Version floors.** The script's own `retalk receive --follow --interval
  --quiet` with repeatable `--peer` needs **retalk 0.2.0+**;
  `--passphrase-path` needs **retalk 0.3.0**. Drop `--passphrase-path` on
  a `--no-passphrase` identity. On an older retalk, drop it as well and export
  `RETALK_PASSPHRASE` in the same shell before calling the script (**init**
  Session rule 8 and §1).
- The writer keeps writing the older `<user>/inbox.ndjson` as well, so a consumer
  still pointed at that path keeps working; pass `--no-legacy` to `start` once
  nothing reads it.
- **Codex + `codex-with-daemon` only:** if the user starts their Codex sessions
  through the `codex-with-daemon` launcher (so idle sessions can be woken, see
  init step 4d), add `--wake-codex` to the `start` command. Each
  delivered message then also nudges the idle session awake, best-effort and
  silent when no daemon is reachable. Do not add the flag otherwise; hooks
  alone deliver at the next prompt or end of turn, and waking is the user's
  opt-in.
- For a rapid live exchange, stop and start again with `--interval 5`; the
  default 60 is the calm rate for all-session listening.
- `status` also prints the tail of this session's spool, so it answers "is it
  running and what has arrived" in one call.

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
ExecStart=/bin/sh -c 'retalk receive --peer <peer> --follow --interval 60 --quiet --dir <user>/identity --passphrase-path <user>/passphrase | python3 <plugin>/bin/spool-writer.py --user <user>'
Restart=always
Environment=RETALK_SAVE_MESSAGE=1
```
Drop `--passphrase-path` if the identity has no passphrase. systemd can also
carry the path in the environment instead, which is the same contract:
`Environment=RETALK_PASSPHRASE_FILE=<user>/passphrase`. Never put the
passphrase itself in a unit file — the file is world-readable by default.

## Next
- **send** — reply to the sender (or the whole room with `--group`).
- **contacts** — see who's saved.
- **group** — see or adjust a room's members.
- **block** — drop an unwanted sender.
- **id** — issue an invite code and watch for a new peer to register themselves.
