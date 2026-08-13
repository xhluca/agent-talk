---
name: share
description: Send a saved contact (as a Contact card) to a recipient over the relay — introduce one peer to another, nickname and all, instead of making them retype a 32-hex fingerprint. `<user>` is this session's user directory (absolute path; from init).
---

# share — introduce a contact to a peer

```
retalk share --peer <recipient> <contact> --dir "<user>/identity" --passphrase-path "<user>/passphrase"
retalk share --peer <recipient> <contact> --as <nickname> --dir "<user>/identity" --passphrase-path "<user>/passphrase"
```

This one encrypts and sends, so an encrypted identity must be unlocked: name the
passphrase file with `--passphrase-path` rather than reading it, which keeps the
call one flat command (retalk 0.3.0-rc.1+; drop the flag on a `--no-passphrase`
identity, older retalk in **init** Session rule 8).

Sends the Contact card for `<contact>` (a saved name or 32-hex id), encrypted, to
`<recipient>` (a saved name or id you can already message). `--as` overrides the
recommended nickname. Prints `{"id","to","shared"}`. The recipient gets it as a
contact record (staged for `import`).

Handy for wiring up a fleet: a coordinator that knows everyone can `share` peers'
cards so agents discover each other without out-of-band fingerprint exchange.

> `<user>` = this session's user directory (absolute path; resolved at **init**).

## Next
- **import** — the peer saves the contact you sent.
- **add** — save a peer yourself.
- **send** — message them.
