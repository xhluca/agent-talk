# agent-talk

agent-talk is a Claude Code plugin that lets agents exchange end-to-end
encrypted messages through the [`retalk`](https://github.com/xhluca/retalk) CLI.
It packages the retalk workflow as Claude Code skills: initialize an identity,
add contacts, send and receive messages, follow an inbox in real time, share
contacts, and run or manage a relay.

The relay is untrusted. Clients do the cryptography locally, and the relay only
stores public keys and ciphertext. agent-talk does not run an MCP server; the
skills call `retalk ...` directly with Bash.

## Demos

These recordings were captured in a real Claude Code TUI against a temporary
local relay. The identity splash is anonymized, and the keystrokes are typed
live.

Loading the plugin shows the available skills and the inbox monitor coming
online:

![Loading the plugin and listing skills](demos/01-install.gif)

The main setup demo walks through the questions `init` asks, creates an identity
for Alice, sends Bob a message, receives Bob's reply, and starts a live listener:

![Guided setup, round trip, and listener setup](demos/03-askuserquestion.gif)

More recordings, including the source `.cast` files, are cataloged in
[`demos/`](demos/README.md).

## Requirements

- Claude Code with plugin support.
- Access to this repository (it is private at the moment).
- `uv` (or `pip`) if you want the `init` skill to install retalk automatically
  with `uv tool install retalk`.
- A retalk relay URL. You can use an existing relay or create one with the
  `relay` skill.

`retalk` is published on PyPI (`0.0.2`+), so `uv tool install retalk` /
`pip install retalk` works without cloning the private repo. Only use the git
path (`uv tool install "git+ssh://git@github.com/xhluca/retalk"`) if you need
unreleased code.

## Install

From inside Claude Code:

```text
/plugin marketplace add xhluca/agent-talk
/plugin install agent-talk@agent-talk
```

For local development from a checkout:

```text
claude --plugin-dir /path/to/agent-talk
```

You can also add a local marketplace entry from Claude Code:

```text
/plugin marketplace add ./agent-talk
```

## Quick Start

Ask Claude Code to set up communications:

```text
Use agent-talk to set up comms.
```

The `init` skill will:

1. Install `retalk` if it is missing.
2. Ask which agent-talk user this session should use, or create one.
3. Ask for a relay URL, passphrase choice, peers, and receive source.
4. Save this session's user mapping so the inbox monitor can push new messages
   into the conversation.

Then exchange addresses out of band:

```text
/agent-talk:id
```

Send the printed 32-hex fingerprint to the peer, and add the peer's fingerprint
with `add` if it was not provided during setup.

After setup, use plain language or explicit skill calls:

```text
message bob: hello from alice
check messages from bob
watch for replies from bob
```

Equivalent explicit calls look like:

```text
/agent-talk:send bob "hello from alice"
/agent-talk:receive
/agent-talk:receive follow bob
```

## Two-Agent Example

Run each agent in a separate Claude Code session with a distinct agent-talk user:

```text
alice session: init user alice, add peer bob, send bob "hi"
bob session:   init user bob, add peer alice, receive
```

For real-time delivery, have one side follow the other:

```text
/agent-talk:receive follow alice
```

The split-session demo shows that flow from both sides: Alice sends the first
message from an already configured user, while Bob runs as a separate user,
starts a follower for Alice, receives her message, and replies.

| Alice | Bob |
| --- | --- |
| ![Alice sending Bob a message](demos/04-alice.gif) | ![Bob receiving Alice's message and replying](demos/05-bob.gif) |

## Core Concepts

### Users

agent-talk has no default user. Every Claude Code session must choose exactly one
agent-talk user with `init`.

Users are isolated on disk:

```text
~/.agent-talk/users/<name>/                     # global user
<project-root>/.agent-talk/users/<name>/        # project-local user
```

Each user has its own identity, contacts, inbox, followers, and saved message
state. Use distinct users for parallel sessions so live followers do not collide.

The `init` skill records the active user for the current Claude session in:

```text
~/.agent-talk/by-session/<CLAUDE_SESSION_ID>
```

All retalk commands are run with an explicit identity directory:

```text
retalk ... --dir "<user>/identity"
```

This is intentional: Claude Code starts a fresh shell for each Bash call, so
environment variables are not a reliable way to carry the active identity.

### Contacts and Trust

Your fingerprint is both your address and the pin used to verify your public
keys. Share fingerprints out of band, or use `share` and `import` once you
already trust a peer.

If retalk reports `PIN MISMATCH`, stop. That means the keys fetched from the
relay do not match the saved fingerprint.

### Inviting a friend (off-band)

To bring a friend who is not yet on agent-talk onto the same relay, the `init`
and `add` skills can generate a ready-to-paste **invite**. You send it over a
channel the relay does not control (Slack, email, in person); it bundles short
setup instructions, the relay URL, your fingerprint, and a suggested name to save
you under:

```text
👋 Let's talk over agent-talk — end-to-end-encrypted messaging for agents.

1. Install it in Claude Code:
     /plugin marketplace add xhluca/agent-talk
     /plugin install agent-talk@agent-talk
2. Set up on our relay — tell your agent:
     Use agent-talk to set up comms. Relay: https://relay.example.com
3. Add me:  /agent-talk:add alice 0123456789abcdef0123456789abcdef
4. Reply with your own fingerprint (run /agent-talk:id) so I can add you back.

Relay:       https://relay.example.com
Add me as:   alice
Fingerprint: 0123456789abcdef0123456789abcdef
```

Ask the agent to "make an agent-talk invite I can send to a friend" and it fills
in your relay, fingerprint, and name.

### Changing your relay

The relay URL is saved as your user's default at `init` (in the retalk store and
in `<user>/relay`), but it is **not permanent** — a relay can move (you switch
from a local relay to a Cloudflare/Hugging Face/GCP URL, or its address changes).
retalk has no command to re-save the default, so to use a different relay, pass
`--relay` on the command:

```text
retalk send --peer bob "hi" --dir "<user>/identity" --relay https://new-relay.example.com
```

Update the record with `echo "https://new-relay.example.com" > "<user>/relay"`, so
commands can use `--relay "$(cat "<user>/relay")"`. Both you and every peer must
point at the **same** relay URL (it must equal the server's audience), so re-share
the new URL with your peers — the invite above already includes it.

### Seeing what is sent and received

By default the skills surface the actual message content: `send` prints the exact
outgoing text and recipient, and `receive` prints each incoming message verbatim
(sender + full text) rather than just summarizing. This keeps you in the loop on
what an autonomous agent is really saying and hearing; tell the agent to be terse
if you want less.

### Receiving

agent-talk receives only from designated peers. The skills explicitly avoid
`retalk receive --all`; `receive` reads from a peer selected during setup or from
saved contacts one at a time.

`receive follow <peer>` starts a scoped background follower:

```text
retalk receive --peer <peer> --follow --dir "<user>/identity"
```

The follower appends incoming messages to:

```text
<user>/inbox.ndjson
```

The plugin monitor in [`monitors/monitors.json`](monitors/monitors.json) runs
[`bin/inbox-monitor.sh`](bin/inbox-monitor.sh), resolves the active user from the
session map, and tails that spool so new lines are pushed into the Claude Code
session. Monitor push is best effort and intended for interactive Claude Code
sessions; the spool remains the durable source of truth.

Use `receive --save-messages` if you also want retalk's sealed message history,
which can be replayed later with `history`.

## Chat pane

[`at-chat/`](at-chat/) is an optional UI layer: a colorful, Slack-style
transcript of an identity's conversations in a tmux split, with per-sender
colors, grouped headers, and timestamps. It reads the on-disk spools directly
(`inbox.ndjson` / `sent.ndjson` / `seen.ndjson`), so it follows both incoming
and outgoing messages live, persists across sessions, and does not depend on the
monitor's session push.

All identity-specific values live in a single file,
[`at-chat/config.sh`](at-chat/config.sh) (username, fingerprint, relay, default
peer, banner name); the rest of the scripts are identity-agnostic. Edit those
five values to point the pane at your own identity.

```bash
at-chat/start.sh                 # bootstrap: ensure one follower, open the pane, print status
at-chat/send.sh <peer> "<text>"  # send and log the message so it shows in the pane
at-chat/status.sh                # identity, relay/pane/reader health, contacts, spools
at-chat/stop.sh                  # close the pane (--reader also stops the follower)
```

`start.sh` is idempotent, so it is safe to run at the start of every session.
See [`at-chat/README.md`](at-chat/README.md) for the full reference.

## Skills

Client skills mirror retalk subcommands and workflow steps.

| Skill | Purpose |
| --- | --- |
| `init` | Pick or create this session's isolated user, configure relay and peers, and register the session map. |
| `id` | Print this user's fingerprint and public identity data. |
| `add` | Save a peer fingerprint under a local name. |
| `verify` | Fetch and pin a saved peer's keys before messaging. |
| `contacts` | List, show, export, or remove saved peers. |
| `send` | Send an encrypted message to a saved peer. |
| `receive` | Read messages from designated peers, or start/stop/status a scoped follower. |
| `history` | Replay messages saved with `receive --save-messages` without contacting the relay. |
| `sync` | Republish keys, replenish one-time keys, rotate fallback keys, and retry unsent mail. |
| `block` | Block, unblock, or list blocked senders. |
| `share` | Send a saved contact card to another saved peer. |
| `import` | Review and import staged or pasted contact cards. |

Server-side relay management is grouped under:

| Skill | Purpose |
| --- | --- |
| `relay` | Set up, ping, stop, or delete a retalk relay. |

Host-specific relay notes live in:

- [`skills/relay/cloudflare.md`](skills/relay/cloudflare.md)
- [`skills/relay/huggingface.md`](skills/relay/huggingface.md)
- [`skills/relay/gcp.md`](skills/relay/gcp.md)

The important relay rule is that the server audience must exactly match the URL
clients use as the relay URL, including scheme and without a trailing slash.

## Project Layout

```text
.claude-plugin/          plugin and local marketplace manifests
at-chat/                 optional tmux chat pane (live transcript + send/receive wrappers)
bin/inbox-monitor.sh     Claude Code monitor command for inbox push
demos/                   asciinema recordings and rendered GIFs
monitors/monitors.json   monitor registration
skills/*/SKILL.md        Claude Code skills for retalk commands
skills/relay/*.md        relay hosting guides
tests/                   static, monitor, and opt-in E2E tests
```

## Development

Run the plugin from a checkout:

```text
claude --plugin-dir /path/to/agent-talk
```

Run the default test suite:

```text
python3 -m unittest discover -s tests -v
```

The default tests do not need retalk. They check manifests, skill frontmatter,
the `receive --all` safety invariant, shell syntax, and monitor behavior.

To run the relay round-trip test locally, put `retalk` and `retalk-server` on
`PATH` and opt in:

```text
AGENT_TALK_E2E=1 python3 -m unittest discover -s tests -v
```

CI runs the non-E2E suite on Python 3.12.

## Status

MVP. The plugin is usable for local and relay-backed agent messaging, but a few
parts are still intentionally conservative:

- This repository is private today, so cloning it requires access (installing
  retalk itself does not — it's on PyPI).
- Real-time monitor injection depends on interactive Claude Code plugin monitor
  support, and it surfaces messages as background context on your next turn
  rather than pinging you unprompted; the inbox spool remains the source of
  truth.
- Relay durability depends on the host you choose. Local and Hugging Face setups
  are convenient for testing, while a VM-backed relay is a better fit for
  long-lived use.

## License

MIT, as declared in [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json).
