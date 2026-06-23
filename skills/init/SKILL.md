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

## 1. Ensure retalk is installed
`retalk --help`; if missing, install from **PyPI**: `uv tool install retalk` (or
`pip install retalk`). Do **not** `git clone` it — the repo is private, so the
git path needs SSH/credentials and fails over HTTPS. Only fall back to
`uv tool install "git+ssh://git@github.com/xhluca/retalk"` if you specifically
need unreleased code.

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
- Ask the **name** and **scope** (default **local** if `./.agent-talk` already
  exists, else **global**); `<user>` = `<scope>/users/<name>`.
- **On-disk name clash** (that dir exists): reuse it instead, or pick a free name
  (e.g. `<name>-2`).
- Ask the **relay URL** — everyone who talks to each other must share ONE relay
  (it equals that server's audience). Pick the case that fits, most common first:
    - **Joining people who already use agent-talk:** paste the relay URL they
      gave you (it's in their invite). You do NOT stand up your own.
    - **A shared/team relay exists:** paste that URL.
    - **You're the first / have none:** create one with the `relay` skill, then
      use its URL here.
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

From now on **this session is `<user>`** — pass `--dir "<user>/identity"` on every
command (and `RETALK_PASSPHRASE=<secret>` if encrypted). Next: share your `id`;
then `send` / `receive` autonomously.
