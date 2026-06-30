---
description: Set up or resume THIS session's retalk user — from your existing users (global ~/.agent-talk or project-local ./.agent-talk) or a new one. Use for first-time setup, to pick which identity this session acts as, or when a command fails with "no identity". agent-talk has no default user; pick one with AskUserQuestion (distinct per parallel session). All human input (relay, passphrase, peers, receive source) is gathered here so send/receive run autonomously afterward.
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
are already saved. Run the guard (step 3) and the session map (step 4).

### Create a new user
- Ask the **name** — **always ask; never assume** a name like `alice`/`bob`.
  Suggest a **unique** name in case several users share this device:
  `<you>-<device>-<n>`, e.g. `sam-macbook-1`. Then ask the **scope** (default
  **local** if `./.agent-talk` already exists, else **global**); `<user>` =
  `<scope>/users/<name>`.
- **On-disk name clash** (that dir exists): reuse it instead, or bump the suffix
  (e.g. `sam-macbook-2`).
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
  Then ask the **passphrase** (no-passphrase recommended; else prefix later
  commands with `RETALK_PASSPHRASE=<secret>`).
- Create the identity:
```
retalk init --dir "<user>/identity" --relay <RELAY_URL> --no-passphrase --display-name <name>
```
- **Publish your keys to the relay** so peers can reach you right away. `retalk
  init` is offline — until you publish, anyone messaging or verifying you hits
  `unknown peer or no published keys`. One `sync` publishes them (re-run it any
  time the relay was reset):
```
retalk sync --dir "<user>/identity"
```
- Record the relay (canonical source for the invite + relay changes — see §5):
```
echo "<RELAY_URL>" > "<user>/relay"
```
- If the scope is **local** and inside a git repo, keep keys out of git:
```
root="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$root" ] && { grep -qxF '.agent-talk/' "$root/.gitignore" 2>/dev/null || echo '.agent-talk/' >> "$root/.gitignore"; }
```
- Front-load peers (AskUserQuestion for each local name + 32-hex fingerprint):
```
retalk add <peer_name> <peer_fingerprint> --dir "<user>/identity"
```
- **Verify** each added peer to pin their keys (best-effort). It needs the peer
  to have published already; if they haven't, skip it — the first message
  verifies their keys on the fly:
```
retalk verify <peer_name> --dir "<user>/identity" \
  || echo "<peer_name> isn't on the relay yet — retalk will verify on first contact"
```
- Choose who to RECEIVE from (safety — agent-talk never uses `--all`): a specific
  peer (usual) or all saved contacts:
```
echo "<peer-name-or-fingerprint>" > "<user>/receive-from"    # or: echo "*contacts*" > "<user>/receive-from"
```

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
invite, handed over a channel the relay doesn't control (Slack, email, …). retalk
builds it from your own card (relay + fingerprint + suggested name) — no manual
assembly:
```
retalk id --invite-message --as <name-they-save-you-as> --dir "<user>/identity"
```
Print that block for the human to copy. It's retalk-generic (install retalk, set
the relay, `retalk add` you, send their id back). For a friend who'll use the
agent-talk **plugin** instead of the raw CLI, tell them to install the plugin
(`/plugin marketplace add xhluca/agent-talk` → `/plugin install
agent-talk@agent-talk`), "Use agent-talk to set up comms" with that relay, then
`/agent-talk:add <name> <fingerprint>`. To share your identity as JSON instead
(the peer saves it with **import**): `retalk id --card --dir "<user>/identity"`.
Offer this whenever the user wants to invite someone.

From now on **this session is `<user>`** — pass `--dir "<user>/identity"` on every
command (and `RETALK_PASSPHRASE=<secret>` if encrypted). Next: share your `id`;
then `send` / `receive` autonomously.
