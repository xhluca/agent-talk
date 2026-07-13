---
name: config
description: Show or set owner-wide retalk defaults in ~/.retalk/config.json (machine-wide, not per-session) — mainly the default relay used as the last fallback. Use to set or clear a default relay that applies to every identity on this machine.
---

# config — owner-wide defaults (default relay)

```
retalk config                                    # show ~/.retalk/config.json
retalk config --relay https://relay.example.com  # set the default relay
retalk config --relay ""                         # clear the default relay
```

Owner-wide (machine-wide), **not** per-session — so **no `--dir`**. The default
relay is the **last fallback**: a `--relay` flag, `RETALK_RELAY`, and the relay
saved in an identity at **init** all override it. retalk ships a built-in default
of `https://retalk-relay.mcgill-nlp.org`, so a fresh setup can talk without
configuring a relay. `RETALK_HOME` relocates the file.

> Per-session identities still set their own relay at **init**; use this only to
> change the machine-wide fallback shared by all identities.

## Next
- **init** — create an identity using the default.
- **relay** — host your own.
- **send** — start messaging.
