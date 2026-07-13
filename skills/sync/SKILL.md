---
name: sync
description: Reconcile this identity with the relay — republish keys, replenish one-time keys, rotate the fallback, and resend unacknowledged mail. Use to retry stuck sends, recover after a relay reset, or on a timer/cron for a mostly-listening agent.
---

# sync — reconcile with the relay

```
retalk sync --dir "<user>/identity"
# -> {"unclaimed","republished","replenished","fallback_rotated","resent"}
```

`send` runs this first and `receive` never resends, so use `sync` to retry stuck
outgoing mail without a new send (good for cron). Target the identity inline with
`--dir "<user>/identity"` (relay is saved in the store and can **change after
init** — add `--relay <URL>` if yours moved; add `RETALK_PASSPHRASE=<secret>` if
encrypted). Cron:
```
*/5 * * * * retalk sync --dir "<user>/identity"
```

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **send** — now that keys are republished.
- **receive** — drain mail.
- **id** — share your reachable id.
