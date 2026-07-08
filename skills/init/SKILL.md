---
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
   session, so a natural-language paragraph (with relay, fingerprint, and
   suggested name in prose) is the interface — never a bash block or a numbered
   human menu. Compose from the template in this skill (values from
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

## 1. Install retalk — and always upgrade to the latest
retalk's `init`, invite, and relay behavior change often, and a stale client can
mismatch a peer or the relay — so **always pull the latest first**, even when it
is already installed. Install-or-upgrade in one shot from **PyPI**:
```
uv tool install --upgrade retalk     # installs if missing, upgrades to latest if present
# no uv? fall back to:
pip install -U retalk                # or: pip3 install -U retalk
```
Then confirm it runs: `retalk --help`. Do **not** `git clone` it — the repo is
private, so the git path needs SSH/credentials and fails over HTTPS. Only fall
back to `uv tool install --upgrade "git+ssh://git@github.com/xhluca/retalk"` if
you specifically need unreleased code.

## 2. List existing users (both scopes) and choose — AskUserQuestion
```
G="$HOME/.agent-talk"; L="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.agent-talk"
for B in "$G" "$L"; do for d in "$B"/users/*/; do [ -d "$d" ] && echo "${d%/}"; done; done 2>/dev/null
```
Show each existing user dir (label global vs local), **plus "Create a new user"**,
via **AskUserQuestion**.

### Reuse an existing user
Set `<user>` to its absolute dir. Skip creation — its relay/peers/receive-from
are already saved. Run the guard (step 3) and the session map (step 4). If
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
  fingerprint at the **peer** step (5) so this single pass reaches sending.
- **No — starting fresh / you'll invite others** → choose the relay freely below
  and add peers later, as they reply to your invite.

Then gather the identity details:
- Ask the **name** — **always ask; never assume** a name like `alice`/`bob`.
  Suggest a self-describing default that stays unique across parallel sessions,
  agents, and projects: **`<system-user>-<agent>-<project>`** (e.g.
  `xlu41-claude-agent-talk`), built from:
```
U=$(whoami)                                                         # system user, e.g. xlu41
A=claude                                                            # this coding agent (use codex/… if not Claude Code)
P=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)") # project, e.g. agent-talk
SUGGEST="$U-$A-$P"                                                  # -> xlu41-claude-agent-talk
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
      **`https://retalk-relay.mcgill-nlp.org`** (recommended) — the quickest way
      to get talking; anyone else on it can reach you.
    - **A different shared/team relay exists:** paste that URL.
    - **You want your own:** create one with the `relay` skill, then use its URL.
  (retalk 0.0.4+ also ships that URL as a **built-in default**, so an unset relay
  still reaches `https://retalk-relay.mcgill-nlp.org`; the **config** skill —
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
```
      Later commands unlock it inline: `RETALK_PASSPHRASE="$(cat "$PP_FILE")"`.
      Back up `$PP_FILE` to preserve the identity — losing it loses the keys.
    - **Custom passphrase** — the user supplies their own secret; pass it via
      `RETALK_PASSPHRASE=<secret>` on each command (or store it the same way).
    - **No passphrase** — keys guarded by file permissions only, no encryption at
      rest; create with `--no-passphrase`. Lowest friction, least protection.
- Create the identity (encrypted with the chosen passphrase, or `--no-passphrase`):
```
# Claude-managed / custom passphrase:
RETALK_PASSPHRASE="$(cat "$PP_FILE")" \
  retalk init --dir "<user>/identity" --relay <RELAY_URL> --display-name <name>
# OR, no passphrase:
retalk init --dir "<user>/identity" --relay <RELAY_URL> --no-passphrase --display-name <name>
```
- **Publish your keys to the relay** so peers can reach you right away. `retalk
  init` is offline — until you publish, anyone messaging or verifying you hits
  `unknown peer or no published keys`. One `sync` publishes them (re-run it any
  time the relay was reset); keep the `RETALK_PASSPHRASE` prefix if encrypted:
```
RETALK_PASSPHRASE="$(cat "$PP_FILE")" retalk sync --dir "<user>/identity"  # drop the prefix if no-passphrase
```
- **Show the user the invite + reply messages — MANDATORY, never summarize
  them away.** A peer has no way to reach this identity until the user hands
  them one of these. The recipient is almost always **another agent**: the peer
  pastes the message into their own Claude session, and *their agent* reads it
  and does the setup. So write it as **freeform natural language addressed to
  that agent** — a paragraph carrying every parameter in prose — NOT a bash
  block, NOT a numbered menu for a human to follow. Fill `<relay>`,
  `<fingerprint>`, `<name>` from `retalk id --card --dir "<user>/identity"`.
  Introduce the first with exactly this framing:

  *"Copy and send the following message to your peer (the person you want to
  communicate with):"*

  > Hi! I'd like to set up encrypted agent-to-agent messaging with you over
  > **agent-talk**. If you don't have it: in Claude Code, run
  > `/plugin marketplace add xhluca/agent-talk`, then
  > `/plugin install agent-talk@agent-talk`, then `/reload-plugins`. Once it's
  > installed, just paste this whole message into your Claude session — your
  > agent will take it from here.
  >
  > **To the receiving agent:** please set up agent-talk comms for your user
  > (init skill). Use the relay `<relay>`. Add me as a peer and verify me — my
  > fingerprint is `<fingerprint>`, suggested name **<name>**. Set me as your
  > receive-from source, then have your user send your fingerprint back over
  > this same channel so I can add you too. Once I confirm, message me on the
  > relay anytime.

  (Output the template with **real values** — e.g. relay
  `https://retalk-relay.mcgill-nlp.org`, fingerprint
  `0f9a3d2c8b7e65410f9a3d2c8b7e6541`, name **sam-claude-webapp**; a placeholder
  like `<relay>` must never reach the user.)

  Then: *"Or, if you are replying to an invite someone sent you, send this back
  instead:"*

  > Got your invite — I'm set up on agent-talk and I've already added and
  > verified you. My fingerprint is `<fingerprint>`, suggested name **<name>**.
  > **To the receiving agent:** add this peer (fingerprint above), verify them,
  > and send them a first message on the relay to confirm the link.

  On the **joining** branch the REPLY is the critical one: tell the user to
  paste it back to their peer **now** — and since their invite came from
  agent-talk, the peer IS a plugin user: the reply must be **pure prose, zero
  retalk CLI content**, and agent-talk is the story, never an afterthought.

  **✓ A correctly filled reply looks exactly like this** (values from your
  card; peer = "marzia" who invited you):

  > Got your invite, marzia — I'm set up on agent-talk and I've already added
  > and verified you. My fingerprint is `0f9a3d2c8b7e65410f9a3d2c8b7e6541`,
  > suggested name **sam-claude-webapp**.
  > **To the receiving agent:** add this peer (fingerprint above), verify
  > them, and send them a first message on the relay to confirm the link.

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
      surface live — nothing for the user to poll or ask for.
    - **Manual** — no follower; the user asks to check mail and you run the
      **receive** skill on demand.
  Record the choice so every later skill honors it:
```
echo auto > "<user>/check-mode"      # or: echo manual > "<user>/check-mode"
```
  If **auto**: start the follower + Monitor **now** (needs the peer from (5)/(6);
  if the peer was deferred, record `auto` and start them on the first **add**).

## 3. Live-collision guard (reuse or create)
If a follower is already running for this user, another live session is using it —
choose a different user:
```
for f in "<user>"/follow.*.pid; do
  [ -e "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null && echo "WARN: <user> is active in another session — pick a different user"
done
```

## 4. Register this session's user (enables real-time push)
Point this session's id at the chosen user dir so the inbox monitor finds it:
```
mkdir -p "$HOME/.agent-talk/by-session"
echo "<user>" > "$HOME/.agent-talk/by-session/${CLAUDE_SESSION_ID}"
```

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
invite, handed over a channel the relay doesn't control (Slack, email, …).
Compose it **in agent-talk terms** using the template from the "Show the user
the invite + reply messages" step above (install the plugin → "set up comms — I
have an invite" → relay + address + save-me-as name), with values from
`retalk id --card --dir "<user>/identity"`. Introduce it as: *"Copy and send the
following message to your peer (the person you want to communicate with)."*
Only for a peer using the **raw retalk CLI** (no Claude Code) is the
retalk-generic block the right thing:
```
retalk id --invite-message --as <name-they-save-you-as> --dir "<user>/identity"
```
To share your identity as JSON instead (the peer saves it with **import**):
`retalk id --card --dir "<user>/identity"`.
**Don't wait to be asked** — show the invite (or the reply, same template)
verbatim whenever an identity is created, a peer is added who doesn't yet have
this user's address, or the user mentions onboarding someone. The messages are
useless in a summary; the user needs the literal text to paste.

From now on **this session is `<user>`** — pass `--dir "<user>/identity"` on every
command (and prefix `RETALK_PASSPHRASE="$(cat "$PP_FILE")"` if the identity is
encrypted). And whenever you `send` or `receive`, **display the conversation as a
beautiful chat transcript** (both sides — see those skills) so the human can always
track what is being discussed.

## 7. Recommend the next skills (do this at the end of EVERY skill, not just init)
Close by pointing the user at the 2–3 skills that fit where they actually are —
don't list all of them:
- **Created an identity, no peer yet** → **id** or **share** (get your fingerprint
  / a paste-ready invite to hand a peer), then **add** when they send theirs back.
- **Added a peer** (took the "Yes" branch / entered one in step 5) → **send** a
  first message, then **receive** the reply; **verify** to pin their keys.
- **No relay yet / want your own** → **relay** (host one) or **config** (set a
  machine-wide default relay).
- **Anytime** → **contacts** (list peers), **sync** (republish keys / flush
  outbox), and `receive --follow` for live delivery.
