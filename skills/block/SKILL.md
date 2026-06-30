---
description: Block a sender so their messages are dropped before decryption (and the relay is told to refuse their resends); re-allow one with `--remove`, or list blocked senders with `--list`. Use to stop unwanted or abusive mail from a specific sender, undo a block, or audit your block list. If the sender is not specified, ask with AskUserQuestion.
---

# block — drop a sender (`--remove` to re-allow, `--list` to audit)

```
retalk block <name-or-fingerprint> --dir "<user>/identity"            # block
retalk block --remove <name-or-fingerprint> --dir "<user>/identity"  # re-allow (unblock)
retalk block --list --json --dir "<user>/identity"                   # list blocked senders
```

Blocking drops a sender's incoming mail during `receive` **before any
decryption** (so they can't consume a one-time key), and tells the relay to
refuse their resends. Local to this identity. If no sender was named, use
**AskUserQuestion**. Target the identity inline with `--dir "<user>/identity"`.

- `--remove <name-or-fingerprint>` re-allows a sender (a no-op if they aren't blocked).
- `--list --json` prints the current block list (one `{"fingerprint","name"}` per line).

(agent-talk receives only from designated peers, so a blocked sender is already
excluded from reads; block additionally tells the relay to refuse that sender's
resends.)

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **contacts** — review saved peers.
- **receive** — read remaining mail.
