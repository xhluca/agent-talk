---
description: List saved peers (your address book) and whether each is verified, show one peer as a shareable JSON Contact card, or remove a saved peer. Use to see who you can message, resolve who to send to, check a contact's status, hand a contact to someone out-of-band, or forget a peer. `<user>` is this session's user directory (absolute path; from init).
---

# contacts — list, show, or remove saved peers

```
retalk contacts --json --dir "<user>/identity"
# one {"name","fingerprint","identity_key","signing_key","verified"} per line

retalk contacts --show <name-or-id> --json --dir "<user>/identity"               # one Contact card
retalk contacts --show <name-or-id> --as <nickname> --json --dir "<user>/identity"

retalk contacts --remove <name-or-id> --dir "<user>/identity"                    # forget a peer
```

Local-only — no relay contact, no passphrase.

- **List** (`--json`): your whole address book, one Contact per line. Use it to
  resolve who to **send** to. Empty means no peers yet — run **add** (or
  **init**'s peer step).
- **Show** (`--show <name-or-id>`): just one contact. Without `--json` it prints
  a status row (`name<tab>fingerprint<tab>verified|unverified`); with `--json` it
  prints the full **Contact card** — `{fingerprint, name, identity_key,
  signing_key, verified}`, where the key fields are `""` until you've **verify**'d
  that peer. `--show` also accepts a raw 32-hex id you haven't saved (a minimal,
  unverified card). `--as <nickname>` overrides the recommended nickname. The
  card is **not a secret** (the keys are public; the fingerprint pins them) — hand
  it to someone out-of-band, or `share` it over the relay (they save it with
  `import`).
- **Remove** (`--remove <name-or-id>`): delete a saved peer (the inverse of
  **add**); a fingerprint drops every name pinned to it. Removing nothing is an
  error.

Target the identity inline with `--dir "<user>/identity"`.

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **add** — save a new peer.
- **verify** — pin a contact's keys.
- **send** — message one.
