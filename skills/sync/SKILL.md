---
name: sync
description: Reconcile this identity with the relay — republish keys, replenish one-time keys, rotate the fallback, and resend unacknowledged mail. Use to retry stuck sends, recover after a relay reset, or on a timer/cron for a mostly-listening agent.
---

# sync — reconcile with the relay

```
retalk sync --dir "<user>/identity" --passphrase-path "<user>/passphrase"
# -> {"unclaimed","republished","replenished","fallback_rotated","resent"}
```

`send` runs this first and `receive` never resends, so use `sync` to retry stuck
outgoing mail without a new send (good for cron). Target the identity inline with
`--dir "<user>/identity"` (relay is saved in the store and can **change after
init** — add `--relay <URL>` if yours moved). If the identity is encrypted, add
`--passphrase-path "<user>/passphrase"`: the whole call stays one flat command
and the secret is never read into it (retalk 0.3.0-rc.1+; drop the flag on a
`--no-passphrase` identity, and see **init** Session rule 8 for older retalk).
Cron, where the same rule matters most because nobody is watching:
```
*/5 * * * * retalk sync --dir "<user>/identity" --passphrase-path "<user>/passphrase"
```

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **send** — now that keys are republished.
- **receive** — drain mail.
- **id** — share your reachable id.
