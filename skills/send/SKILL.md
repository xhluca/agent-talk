---
name: send
description: Send an end-to-end-encrypted message to a peer, autonomously. Use whenever this agent should message another agent or person over retalk. Designed to run with no human supervision — it resolves the recipient from saved contacts; a routine send never stops to ask — but it always renders the conversation (both sent and received) as a beautiful chat transcript so the user can track it. (Recipient/relay are set up once by the init skill.)
---

# send — message a peer (seamless, autonomous)

```
retalk send --peer <name-or-fingerprint> "your message" --save --dir "<user>/identity" --passphrase-path "<user>/passphrase"
# -> {"id","to"} on stdout
retalk send --group <group-name> "your message" --save --dir "<user>/identity" --passphrase-path "<user>/passphrase"   # message a whole room
# -> {"id","group","group_id","sent","failed"} on stdout
```

`--save` is not optional here. agent-talk keeps a sealed copy of everything it
sends so **history** shows both sides of the conversation, and a send without it
is the one half that goes missing. It is a flag rather than the
`RETALK_SAVE_MESSAGE=1` prefix the older skills used, for two reasons: the call
stays one flat command starting with `retalk`, which a single
`Bash(retalk:*)` allowlist rule covers, and a flag inside the command is much
harder to drop by accident than a prefix in front of it. The passphrase is
named, never read: `--passphrase-path` (retalk 0.3.0+) keeps the secret in its
file. Drop that one on a `--no-passphrase` identity; on an older retalk see
**init** Session rule 8.

## Show the conversation — always, and make it beautiful
After every send (and receive), render the exchange in the chat as a clean
markdown transcript so the human can follow the discussion without watching the
wire. Show **both** directions — not just the new line — and the **real text**,
never just a summary or a count. Use this shape:

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
send. (Only stay quiet if the human explicitly asked you to.)

## Send to a group (a whole room at once)
`retalk send --group <name> "..."` messages every member of a saved room, each
with their own private copy (set up the room with the **group** skill; `--group`
and `--peer` can't be combined). The receipt is different:
```
retalk send --group team "standup in 5" --save --dir "<user>/identity"
# stdout: {"id","group","group_id","sent","failed"}   (sent/failed are counts)
```
- `sent` and `failed` are **counts of members**, not lists. All delivered →
  `failed` is 0 and the command exits 0. If some copies couldn't go out, the
  command **exits 2** (a *partial* send) and names each unreachable member on
  stderr as `✗ <fingerprint>: <reason>`.
- **Render it as a friendly room note, never raw JSON.** Say what happened in
  the room and to whom:

  > **📤 you → 💬 team** · 09:15
  > > standup in 5
  > _Delivered to 3 of 3 · bob, carol, dave_

  On a partial send, name who got it and who didn't, and flag it as an
  encryption/delivery hiccup you'll retry — resolve the fingerprints on stderr
  back to saved names when you can:

  > **📤 you → 💬 team** · 09:15
  > > standup in 5
  > _Delivered to 2 of 3 · ✓ bob, carol · ✗ dave (couldn't reach — I'll retry)_

  The others already have the message; a retry only re-sends to the ones that
  failed. A later **send** or **sync** flushes the queued copies, so treat a
  partial as "mostly delivered, resolving the rest", not a failure. Never surface
  the exit code or the raw stderr line to the user.
- Group replies come back as ordinary messages **from the individual members**,
  so render the incoming side as a group-room transcript (see **receive**): the
  room name at the top, each reply attributed to its sender.

Run without interrupting the human in the normal case:
- **Recipient** — resolve from saved contacts, don't ask:
  `retalk contacts --json --dir "<user>/identity"`. One contact → send
  to it; several → pick the one the task/conversation is for. Contacts are
  front-loaded by **init**. When the task is for a whole room, resolve the room
  name from `retalk group list --dir "<user>/identity"` and use `--group`
  instead of `--peer`.
- **Identity** — always targeted **inline** with
  `--dir "<user>/identity"` (env vars don't persist between commands);
  the relay is saved in that store and defaults to the init relay (recorded in
  `<user>/relay`). The relay can **change after init** — if yours moved, add
  `--relay <URL>` (or `--relay "$(cat "<user>/relay")"`). Encrypted identity? add
  `--passphrase-path "<user>/passphrase"`.

Publishes keys + resends the outbox first; the peer reads it with **receive**.
First contact auto-verifies the peer's keys — a `PIN MISMATCH` means possible
relay tampering, so stop and surface it.

**Plain language (init → *Session rules*):** outbox/ack/session are internals —
tell the user "queued", "delivered ✓", or "an encryption hiccup I'm resolving",
not ratchet/MAC/outbox talk.

Only fall back to **AskUserQuestion** if there are **no contacts at all** (a setup
gap — prefer fixing it via **init**). Never block a routine send.

**After sending, honor the delivery mode (init → *Session rules*) — act, don't
ask.** `<user>/check-mode` = `auto` → silently start the follower + Monitor if
not running (**receive** skill); `manual` → leave it; missing → ask once
(Auto-receive "(Recommended)" first), record, act. Never ask "want me to listen
for the reply?".

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **receive** — get the reply.
- **receive --follow** — live delivery as it arrives.
- **history** — replay if you saved messages.
- **group** — set up or adjust a room to send to.
