---
name: id
description: Print this agent's retalk user id (fingerprint) to share with peers, or to confirm which identity is active. Use whenever you need your own retalk address/fingerprint.
---

# id — your address (fingerprint)

```
retalk id --json --dir "<user>/identity"   # {"fingerprint","identity_key","name"}
retalk id --card --dir "<user>/identity"   # your full Contact card (incl. relay) — shareable; peer saves it via import
retalk id --invite-message --as <name> --dir "<user>/identity"   # a copy-paste invite to onboard a peer off-band
retalk id --invite-reply --as <name> --dir "<user>/identity"     # a paste-back reply: hands an inviter your address
```

The fingerprint is your address and pin in one — safe to post publicly; **share
it out-of-band** and ask the peer for theirs. `--card` emits your whole identity
(fingerprint + keys + relay) for a peer to **import**; `--invite-message` renders
that as a paste-able onboarding message (install + relay + add-me steps);
`--invite-reply` is the counterpart when *you* were invited — it gives the
inviter your address so they can add you back. **Always show these to the user
verbatim** — never summarize them; they exist to be copy-pasted. Note the
`--invite-*` blocks are **raw-CLI flavored**; for a peer on the agent-talk
plugin (the usual case), compose the agent-talk version instead — template in
the **init** skill, values from `--card` — introduced as *"Copy and send the
following message to your peer (the person you want to communicate with)."* Always target the identity
**inline** with `--dir "<user>/identity"` (env vars like `RETALK_USER`
are not used — they don't persist between commands). Encrypted identity? prefix
`RETALK_PASSPHRASE=<secret>`. No relay contact.

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **add** — save a peer once they send their id back.
- **share** — introduce a saved contact to someone.
- **send** — message a peer you know.
