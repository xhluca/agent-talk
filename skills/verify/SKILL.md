---
name: verify
description: Record and pin a saved peer's public keys (explicit first-contact verification). Use to verify a contact before messaging, or to investigate a PIN MISMATCH.
---

# verify — pin a peer's keys

```
retalk verify <peer> --dir "<user>/identity" --passphrase-path "<user>/passphrase"
retalk verify <peer> --identity-key K --signing-key S --dir "<user>/identity" --passphrase-path "<user>/passphrase"
```

Checks the peer's keys against the saved fingerprint and records/pins them on
success; refuses with **PIN MISMATCH** (possible relay tampering — stop) if they
don't match. Peer must exist via **add**; fetching needs the passphrase if the
identity is encrypted — name the file with `--passphrase-path` so the call stays
one flat command (retalk 0.3.0-rc.1+; drop it on a `--no-passphrase` identity,
older retalk in **init** Session rule 8). Target the identity
inline with `--dir "<user>/identity"`.

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **send** — message the now-pinned peer.
- **receive** — read their reply.
- **contacts** — review your saved peers.
