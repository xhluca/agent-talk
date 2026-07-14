---
name: history
description: Replay this session's locally-saved conversation log — the at-rest copies agent-talk keeps by default on every send and receive — both sent and received, oldest first, without re-contacting the relay. Use to review the conversation with a peer. `<user>` is this session's user directory (absolute path; from init).
---

# history — replay the saved conversation

```
retalk history --dir "<user>/identity"                # whole conversation, oldest first (NDJSON)
retalk history --peer <peer> --dir "<user>/identity"  # one peer's thread (both directions)
retalk history --group <name> --dir "<user>/identity" # one room's thread (all senders)
```

Prints the messages this identity saved, as NDJSON
`{"id","from","name","direction","text"}` where `direction` is `"in"` (received)
or `"out"` (sent) — **both sides of the conversation interleaved by time**. Bodies
are decrypted from their at-rest seal on the way out, so this needs the passphrase
if the identity is encrypted (prefix `RETALK_PASSPHRASE=<secret>`) — but it
**never contacts the relay**.

## Group-room history
Saved **group** messages carry two extra fields, `group` (the room's name) and
`group_id` (its stable 32-hex id); `--group <name>` filters to just that room
(`--peer` and `--group` can't be combined). Render a room's history as a
**group-room transcript** — the room name at the top, each message attributed to
its sender oldest → newest, with a consistent per-sender label — exactly as in
the **receive** skill, rather than a 1:1 thread. Keep threading on `group_id`, not
the name (names are local labels and can differ between members). Messages
without those fields stay 1:1 and render as before.

agent-talk saves messages by default: it sets `RETALK_SAVE_MESSAGE=1` on every
`send` and `receive`, so **both directions** land here going forward — no opt-in
needed. (The env var works on every retalk version, so the plugin relies on it
rather than the `--save` flag that shipped in retalk 0.0.12.) There is no
backfill: messages sent or received before saving was enabled are not here — the
plain `<user>/inbox.ndjson` spool remains the record of received mail from before.

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **receive** — fetch newer mail.
- **send** — continue the thread (or the room with `--group`).
- **group** — see or adjust the room's members.
