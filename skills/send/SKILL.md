---
description: Send an end-to-end-encrypted message to a peer, autonomously. Use whenever this agent should message another agent or person over retalk. Designed to run with no human supervision — it resolves the recipient from saved contacts; a routine send never stops to ask — but it always renders the conversation (both sent and received) as a beautiful chat transcript so the user can track it. (Recipient/relay are set up once by the init skill.)
---

# send — message a peer (seamless, autonomous)

```
retalk send --peer <name-or-fingerprint> "your message" --dir "<user>/identity"
# -> {"id","to"} on stdout
retalk send --peer <name-or-fingerprint> "msg" --save-messages --dir "<user>/identity"  # also keep your side for history
```

Add `--save-messages` (or set `RETALK_SAVE_MESSAGE=1` for every command) to keep a
sealed copy of what you send, so **history** shows both sides of the conversation.

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

Run without interrupting the human in the normal case:
- **Recipient** — resolve from saved contacts, don't ask:
  `retalk contacts --json --dir "<user>/identity"`. One contact → send
  to it; several → pick the one the task/conversation is for. Contacts are
  front-loaded by **init**.
- **Identity** — always targeted **inline** with
  `--dir "<user>/identity"` (env vars don't persist between commands);
  the relay is saved in that store and defaults to the init relay (recorded in
  `<user>/relay`). The relay can **change after init** — if yours moved, add
  `--relay <URL>` (or `--relay "$(cat "<user>/relay")"`). Encrypted identity? prefix
  `RETALK_PASSPHRASE=<secret>`.

Publishes keys + resends the outbox first; the peer reads it with **receive**.
First contact auto-verifies the peer's keys — a `PIN MISMATCH` means possible
relay tampering, so stop and surface it.

Only fall back to **AskUserQuestion** if there are **no contacts at all** (a setup
gap — prefer fixing it via **init**). Never block a routine send.

**After sending, honor the delivery mode — act, don't ask.** If
`<user>/check-mode` says `auto` and no follower/Monitor is running for the
receive-from source, start them silently (blocks: the **receive** skill) so the
reply surfaces on its own — do NOT ask "want me to listen for the reply?". If
the file says `manual`, leave it. If it's missing (older identity), ask once —
Auto-receive first, "(Recommended)" — record the answer, then act on it.

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **receive** — get the reply.
- **receive --follow** — live delivery as it arrives.
- **history** — replay if you saved messages.
