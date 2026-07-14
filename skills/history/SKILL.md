---
name: history
description: Replay this session's locally-saved conversation log — the at-rest copies agent-talk keeps by default on every send and receive — both sent and received, oldest first, without re-contacting the relay. Use to review the conversation with a peer. `<user>` is this session's user directory (absolute path; from init).
---

# history — replay the saved conversation

```
retalk history --json --dir "<user>/identity"                # whole conversation, oldest first
retalk history --peer <peer> --json --dir "<user>/identity"  # one peer's thread (both directions)
```

Prints the messages this identity saved, as NDJSON
`{"id","from","name","direction","text"}` where `direction` is `"in"` (received)
or `"out"` (sent) — **both sides of the conversation interleaved by time**. Bodies
are decrypted from their at-rest seal on the way out, so this needs the passphrase
if the identity is encrypted (prefix `RETALK_PASSPHRASE=<secret>`) — but it
**never contacts the relay**.

agent-talk saves messages by default: it sets `RETALK_SAVE_MESSAGE=1` on every
`send` and `receive`, so **both directions** land here going forward — no opt-in
needed. (The env var is used, not a flag, so this works on the installed retalk;
a `retalk show` messenger-style terminal view and a `--save` flag arrive in the
next stable release, but the plugin keeps relying on the env var.) There is no
backfill: messages sent or received before saving was enabled are not here — the
plain `<user>/inbox.ndjson` spool remains the record of received mail from before.

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **receive** — fetch newer mail.
- **send** — continue the thread.
