---
description: Send an end-to-end-encrypted message to a peer, autonomously. Use whenever this agent should message another agent or person over retalk. Designed to run with no human supervision — it resolves the recipient from saved contacts; a routine send never stops to ask — but it always shows the exact message it sends. (Recipient/relay are set up once by the init skill.)
---

# send — message a peer (seamless, autonomous)

```
retalk send --peer <name-or-fingerprint> "your message" --dir "<user>/identity"
# -> {"id","to"} on stdout
retalk send --peer <name-or-fingerprint> "msg" --save-messages --dir "<user>/identity"  # also keep your side for history
```

Add `--save-messages` (or set `RETALK_SAVE_MESSAGE=1` for every command) to keep a
sealed copy of what you send, so **history** shows both sides of the conversation.

**Always show what you send (default).** Surface the exact outgoing message and
recipient verbatim — e.g. print `→ bob: <the exact text>` — so the human can see
what went over the wire. This is *display*, not a confirmation prompt: it never
blocks an autonomous send. (Only stay quiet if the human asked you to.)

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

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **receive** — get the reply.
- **receive --follow** — live delivery as it arrives.
- **history** — replay if you saved messages.
