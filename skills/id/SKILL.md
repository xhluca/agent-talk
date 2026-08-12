---
name: id
description: Print this agent's retalk user id (fingerprint) to share with peers, or to confirm which identity is active, and issue or redeem the invite codes that let a peer register themselves as a contact. Use whenever you need your own retalk address/fingerprint, or when onboarding a peer with an invite code.
---

# id — your address (fingerprint)

```
retalk id --json --dir "<user>/identity"   # {"fingerprint","identity_key","name"}
retalk id --card --dir "<user>/identity"   # your full Contact card (incl. relay) — shareable; peer saves it via import
retalk id --invite-message --as <name> --dir "<user>/identity"   # a copy-paste invite to onboard a peer off-band
retalk id --invite-reply --as <name> --dir "<user>/identity"     # a paste-back reply: hands an inviter your address
retalk invite new --dir "<user>/identity"                        # mint an invite code so a peer can register themselves
```

The fingerprint is your address and pin in one — safe to post publicly; **share
it out-of-band**. Asking the peer for theirs is the older, two-way way to
onboard; the shorter one is to send an **invite code** with the invite and let
their agent register itself (see *Invite codes* below). `--card` emits your
whole identity (fingerprint + keys + relay) for a peer to **import**;
`--invite-message` renders
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

## Invite codes — let a peer register themselves

Without a code, onboarding runs in both directions: you invite a peer, they set
up, they send their fingerprint back, and you **add** it by hand. An invite code
closes that loop. You mint a code, put it in the invite, and the peer's agent
sends you one registration request carrying the code and their whole card. Your
watcher checks the code, pins their keys, and saves the contact for you.

**What a code proves, exactly.** A valid code shows the sender was authorised by
whoever issued it. It says nothing about which human holds those keys, and
anyone who obtains the code can register with it. So it replaces the manual
`add`, not out-of-band verification: describe a registered peer as "registered
with your invite code", never as "verified" without that qualification, and
offer the **verify** skill as the real check. Treat a code as a secret while it
is live, hand it over the same off-band channel as the invite, and revoke one
that leaks.

**Version floor: retalk 0.3.0-rc.1.** Everything in this section needs it. On an
older retalk these commands do not exist, so fall back to the manual path: a
codeless invite, the peer replies with their fingerprint, you **add** them.
Both templates are in the **init** skill. Check once, and say which path you
took:
```
retalk invite --help >/dev/null 2>&1 && echo "invite codes available" \
  || echo "retalk too old for invite codes; use the manual add path"
```
(The **init** skill's install-or-upgrade step normally makes this moot; if it
reports too old, run that step first.)

### Issue a code (inviter)
**Single-use is the default.** Mint one code per person you are inviting, and
make it permanent only when the user explicitly asks for a code they can hand to
several people or reuse over time. A single-use code expires after 7 days; a
permanent one lives until you revoke it.
```
retalk invite new --dir "<user>/identity"                       # single-use, expires in 7 days
retalk invite new --peer <name> --dir "<user>/identity"         # pre-assign the local name the contact is saved under
retalk invite new --permanent --dir "<user>/identity"           # multi-use until revoked; only when asked for
retalk invite new --expires <days> --dir "<user>/identity"      # override the expiry (0 = never)
# stdout, one JSON object: {"code","kind":"single"|"permanent","expires","peer"}
```
Pass `--peer <name>` whenever you already know who the invite is for: the
contact then lands under that local name instead of whatever name the requester
suggests for themselves. Prefix `RETALK_PASSPHRASE=<secret>` if the identity is
encrypted.

Take `code` from that JSON and put it in the invite message (template in the
**init** skill). Then **start the watcher below in the same turn**. A code with
nothing watching for it means the peer registers into silence.

For a peer on the raw retalk CLI with no coding agent, retalk renders its own
invite text with the code appended:
```
retalk id --invite-message --code <code> --as <name-they-save-you-as> --dir "<user>/identity"
```

### See and revoke codes
```
retalk invite list --dir "<user>/identity"                # human table
retalk invite list --json --dir "<user>/identity"         # NDJSON, one object per code
# {"code","kind","peer","created","expires","uses","used_by":[...],"revoked","active"}
retalk invite revoke <code> --dir "<user>/identity"       # deactivate; exit 2 + "[retalk] no such invite code" if unknown
```
`active` means not revoked, not expired, and either permanent or still unused.
Revoke a code the moment the user says it went to the wrong place.

### Watch for registrations (inviter)
`retalk invite watch` reads pending mail **from unknown senders only** and acts
on contact requests. Mail from a saved contact is never touched; it stays for a
normal `receive`. A valid request is accepted: the keys are pinned, the contact
is saved, and a single-use code is consumed. An invalid one is refused, so the
sender's outbox stops resending it. Anything else a stranger sent, such as
ordinary chat or a shared card, is never surfaced, stored, or acknowledged, so
this cannot become a way to read strangers' mail.

**One timing artefact worth knowing, so you never call it a lost message.** The
relay hands mail over on fetch, so the watcher's scan does clear the pending
copy of a stranger message it declines to act on. Nothing was acknowledged, so
the sender's outbox re-delivers it by itself on the next resend cycle, which is
the same at-least-once path that covers a `receive` that died mid-read. Where
this shows up: while the watcher and a message follower are both running for
this identity, a peer's first message can race their own registration and land
while they are still a stranger. It then arrives a cycle late, at the sender's
next send or sync, or about a minute if they are following. Report it as
delayed, never as dropped, and note that stopping the watcher once every code is
redeemed or revoked removes the overlap entirely.

One-shot check (emits no records and exits when nothing is pending; it still
prints a short banner on stderr unless you add `--quiet`):
```
retalk invite watch --dir "<user>/identity"
```
`invite watch <start|stop|status>` — the background watcher, which feeds the
plugin's **contact-request spool** so registrations surface in the session the
way messages do. Start it right after issuing a code:
```
D="<user>"; PID="$D/invite-watch.pid"
if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
  echo "already watching (pid $(cat "$PID"))"
else
  nohup env UD="$D" W="<plugin>/bin/spool-writer.py" bash -c 'while true; do retalk invite watch --follow --interval 10 --quiet --dir "$UD/identity" 2>> "$UD/invite-watch.err" | python3 "$W" --user "$UD" --stream requests 2>> "$UD/invite-watch.err"; sleep 2; done' >/dev/null 2>&1 &
  echo $! > "$PID"; echo "watching for registrations (pid $(cat "$PID"))"
fi
```
```
D="<user>"                                                  # stop
[ -f "$D/invite-watch.pid" ] && kill "$(cat "$D/invite-watch.pid")" 2>/dev/null
pkill -f "retalk invite watch .*--dir $D/identity" 2>/dev/null
rm -f "$D/invite-watch.pid"; echo "stopped watching"
```
```
D="<user>"                                                  # status
[ -f "$D/invite-watch.pid" ] && kill -0 "$(cat "$D/invite-watch.pid")" 2>/dev/null \
  && echo "watching (pid $(cat "$D/invite-watch.pid"))" || echo "not watching"
echo "--- recent registrations (this session) ---"
tail -n 20 "$D/sessions/${CLAUDE_SESSION_ID}.requests.ndjson" 2>/dev/null || echo "(none yet)"
```
- `<plugin>` is this plugin's root (`${CLAUDE_PLUGIN_ROOT}` under Claude Code).
  Prefix the `nohup env` with `RETALK_PASSPHRASE="$(cat "$PP_FILE")"` if the
  identity is encrypted, since the watcher decrypts and so needs it.
- `--interval 10` is a calm default while a code is outstanding; retalk polls
  every 2 seconds if you leave it off. **Stop the watcher** once every code you
  issued has been redeemed or revoked; it exists for the onboarding window, not
  for the whole session.
- The spool writer's `--stream requests` keeps these records in
  `<user>/sessions/<session-id>.requests.ndjson`, separate from message mail, and
  the plugin's `retalk-requests` monitor pushes each new line into the session.
  On hosts without that monitor (see init's *Adapt to your host agent*), read the
  spool with the status block above.

### Acting on what the watcher reports
Two record kinds arrive on that spool. Key off `kind`:
- **`{"kind":"contact_accepted","code","from","name","card"}`** — a peer
  registered. **Tell the user unprompted**: who registered (the `name`, with the
  `from` fingerprint), that the invite code was the only check made, and that
  **verify** is how they confirm the keys belong to the person they meant. Then
  act like the **add** skill's *honor the delivery mode* step: if
  `<user>/receive-from` is unset, write this peer's name to it, and if
  `<user>/check-mode` is `auto`, start the message follower and Monitor
  (**receive** skill) so their first message surfaces. Sending them a short
  hello is a good way to confirm the link, since they have no other way to learn
  they were accepted. If the code was single-use, it is now spent; if it was
  permanent and the onboarding is done, revoke it.
- **`{"kind":"contact_request_rejected","from","reason"}`** — a request was
  refused; `reason` is `unknown-code`, `revoked`, `expired`, `consumed`, or
  `card-mismatch`. Nothing was saved and nothing is pending. Mention it quietly,
  in plain terms ("someone tried to register with a code that had already been
  used"), and only raise it if the user is expecting a specific person, in which
  case the fix is usually a fresh code. The rejected code is never echoed back,
  so you cannot tell the user which one was tried. `card-mismatch` is the one to
  take seriously: the keys did not match the fingerprint they claimed.

### Register with someone else's code (requester)
You were invited and the invite carried a code. Create your identity and publish
your keys first (**init**), then send one request. It adds the inviter as a
contact, pins their published keys, and hands over your card:
```
retalk request <inviter-fingerprint> --code <code> --peer <name-to-save-them-as> --dir "<user>/identity"
# stdout, one JSON object: {"id","to"}  (the same shape as a send receipt)
```
- `<name-to-save-them-as>` is the suggested name from their invite; it is your
  local label for them, and they never learn it.
- **Then wait to be messaged.** Exit 0 means the request was sent, not that it
  was accepted: acceptance happens whenever the inviter's watcher next runs, and
  there is deliberately no way to ask whether a code worked. A silent inviter and
  a refused code look identical from here, on purpose. So **never build a retry
  or status-check loop, and never re-send the request**; say plainly that the
  peer will message when they have accepted, and offer to tell the user if
  nothing has arrived after a while so they can check the code off-band. Do set
  the inviter as `receive-from` and start the listener (**receive** skill) so
  their first message surfaces the moment it lands.
- Failures are local and immediate, and they all exit **2**: tell them apart by
  what lands on stderr, not by the code. A one-line `[retalk] …` message means
  the command was wrong and needs fixing, as in
  `[retalk] request needs --code CODE` or
  `[retalk] an inviter is addressed by their 32-hex user id`. A
  could-not-reach-the-relay block means the relay is unreachable, so retry
  later rather than editing the command. A `PIN MISMATCH` on the inviter's keys
  means stop and tell the user: the relay returned keys that do not match the
  fingerprint in the invite.

## Next
- **add** — save a peer who sent their id back by hand (the codeless path).
- **verify** — pin a registered peer's keys against a fingerprint from off-band.
- **send** — message a peer you know, or say hello to one who just registered.
