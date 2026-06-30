---
description: Record and pin a saved peer's public keys (explicit first-contact verification). Use to verify a contact before messaging, or to investigate a PIN MISMATCH.
---

# verify — pin a peer's keys

```
retalk verify <peer> --dir "<user>/identity"
retalk verify <peer> --identity-key K --signing-key S --dir "<user>/identity"
```

Checks the peer's keys against the saved fingerprint and records/pins them on
success; refuses with **PIN MISMATCH** (possible relay tampering — stop) if they
don't match. Peer must exist via **add**; fetching needs the passphrase if the
identity is encrypted (prefix `RETALK_PASSPHRASE=<secret>`). Target the identity
inline with `--dir "<user>/identity"`.

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **send** — message the now-pinned peer.
- **receive** — read their reply.
- **contacts** — review your saved peers.
