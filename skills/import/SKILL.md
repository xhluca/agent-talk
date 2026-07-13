---
name: import
description: Save a contact someone shared with you (a Contact card) as a local peer. agent-talk does NOT auto-import — review staged cards and import only ones from a peer you trust. `<user>` is this session's user directory (absolute path; from init).
---

# import — save a shared contact (agent decides — be careful)

Importing adds a peer to your address book — a **trust action**. Do **not**
blanket-import. Review first, then import **selectively**, only cards from a
**designated/trusted** peer. retalk re-checks any keys against the fingerprint and
refuses a tampered card with **PIN MISMATCH** (saving nothing).

Cards that peers `share`d arrive via `receive` and are **staged** in a
contact-inbox (not yet saved as peers).

Review what's staged (imports nothing):
```
retalk import --inbox --list --json --dir "<user>/identity"
```
Import just the one you trust (optionally rename):
```
retalk import --inbox <staged-name-or-id> --dir "<user>/identity"
retalk import --inbox <staged-name-or-id> --as <nickname> --dir "<user>/identity"
```
Import a card handed to you directly (JSON argument or stdin):
```
retalk import '<card json>' --dir "<user>/identity"
```

Avoid `retalk import --inbox` with no name (it imports **all** staged cards)
unless you've reviewed them. A keyless card imports as unverified (verified on
first contact).

## After a contact is shared to you: confirm your fingerprint off-band
**Always** prepare a ready-to-paste reply that confirms **your own fingerprint**,
and send it back over a channel the relay doesn't control (Slack, email, in
person) — every time someone shares a contact with you. The relay is untrusted,
so an out-of-band fingerprint is what lets the other side **pin your keys** and
trust it's really you; sharing only over the relay leaves that half open.
```
retalk id --invite-message --as <name-they-save-you-as> --dir "<user>/identity"
```
(Or just your card: `retalk id --card --dir "<user>/identity"`.) For a peer who's
already set up, the part that matters is your fingerprint + "add me as <name>" so
they can `verify`/pin you. Do this even after you've imported them.

> `<user>` = this session's user directory (absolute path; resolved at **init**).

## Next
- **verify** — pin the imported keys.
- **send** — message the imported peer.
- **contacts** — review saved peers.
