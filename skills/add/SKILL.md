---
description: Save a peer's retalk user id (their 32-hex fingerprint), optionally under a local name, so you can message them by name. Use when you have a peer's fingerprint to record. Add --verify to fetch and pin their keys now. If the fingerprint is missing, ask with AskUserQuestion.
---

# add — save a peer

```
retalk add <fingerprint> --peer <name> --dir "<user>/identity"
retalk add <fingerprint> --peer <name> --verify --dir "<user>/identity"   # also fetch + pin their keys now
```

`<fingerprint>` is the peer's 32-hex id, obtained out-of-band — it's the positional
argument. `--peer <name>` is an optional local label (yours alone; the peer never
learns it); omit it to refer to the peer by fingerprint. If the fingerprint is
missing, use **AskUserQuestion**. Re-adding the same fingerprint updates its name.
Target the identity inline with `--dir "<user>/identity"`.

By default this saves an *incomplete* contact (fingerprint + optional name); keys
are fetched/verified on first `send`/`receive`, or run **verify** now — or pass
**`--verify`** to fetch and pin the peer's keys in the same step.

## After adding: honor the delivery mode — act, don't re-ask
The user already chose how messages arrive (at **init**, recorded in
`<user>/check-mode`). **Never end an add with "want me to start a listener?"**
— read the file and act:
- **`auto`** → make this peer covered, silently: if `<user>/receive-from` is
  unset, write this peer's name to it; then, if no follower/Monitor is running
  for the receive-from source, start them (exact blocks: the **receive** skill,
  *Background follow* + *Proactive auto-wake via Monitor*). Just tell the user
  it's live: "replies from <peer> will surface here automatically."
- **`manual`** → do nothing; the user checks mail via **receive**.
- **missing** (identity predates the delivery-mode question) → ask **once** via
  AskUserQuestion — **Auto-receive first, labeled "(Recommended)"** — record the
  answer (`echo auto|manual > "<user>/check-mode"`), then act on it as above.

## After adding: share your address back (off-band) — ALWAYS show the message
A peer you `add` still needs YOUR address to reach you — unless they already have
it (e.g. this add came from *their* invite and you already handed back a reply).
**Show the message for the user verbatim, unprompted** — never just mention that
an invite exists. Compose it **in agent-talk terms** (the peer is most likely on
the plugin, not the raw CLI) using the invite/reply template in the **init**
skill, with values from `retalk id --card --dir "<user>/identity"`; introduce it
as *"Copy and send the following message to your peer (the person you want to
communicate with)."* Only for a raw-CLI peer use the retalk-generic blocks:
```
retalk id --invite-message --as <your-name> --dir "<user>/identity"   # peer not on retalk yet
retalk id --invite-reply --as <your-name> --dir "<user>/identity"     # replying to a peer's invite
```
Or share your identity as JSON for them to **import**:
`retalk id --card --dir "<user>/identity"`. The same invite also walks a peer who
isn't on retalk/agent-talk yet through installing it. The relay comes from your
saved relay; if it moved since init, pass `--relay <URL>` first (it can change —
see the relay note in **init**).

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **verify** — pin the peer's keys off-band.
- **send** — message the peer you just added.
- **id** — hand over your id so they add you.
