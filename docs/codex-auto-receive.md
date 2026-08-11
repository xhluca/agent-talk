# Auto-receive on Codex

## Summary

Auto-receive works on Codex from version 0.147 onward, through Codex's hook
system. In this document, "auto-receive" means an incoming message from a peer
appearing in your active session without any action from you, so that the agent
can respond in the conversation you are already using.

Codex delivers messages at three points: when a session starts, when you submit
a prompt, and when the agent finishes a turn. The third one is what makes
delivery feel automatic. A `Stop` hook that returns `{"decision": "block",
"reason": "..."}` makes Codex create a continuation prompt, which acts as a new
user message, so a peer's message that lands while the agent is working is
handled as soon as the current turn ends, with nothing typed by you.

Hooks alone leave one case open. A session sitting idle at the prompt, with no
turn running and nobody typing, does not wake on its own, because a hook is
something the session calls rather than something that can call the session.
The message waits in the spool and surfaces at the next prompt or the next end
of turn.

That last case can be closed as well, at the cost of some setup: with Codex's
local app-server daemon running, an outside process can push a turn into an
idle session directly. See [Waking an idle session](#waking-an-idle-session)
below. Hooks remain the default because they need no setup at all.

## How it works

1. A background follower. `retalk receive --peer <fingerprint> --follow
   --interval 60 --quiet` decrypts incoming messages, and the plugin's spool
   writer copies each one to this session's spool,
   `<user>/sessions/<session-id>.ndjson`. Neither component depends on the coding
   agent, and both run the same way everywhere.
2. The inbox hook. `extensions/codex/inbox-hook.py` reads the lines added to the
   spool since it last ran and hands them to Codex, as extra context for the
   `SessionStart` and `UserPromptSubmit` events, and as a continuation prompt for
   `Stop`.

Cursors live in `<user>/sessions/.codex-hook-state.json`, keyed by spool path, so
sessions sharing that directory keep separate read positions. Each entry records
the byte offset consumed, a fingerprint of the spool's first bytes (so a spool
truncated and refilled to the same length between runs is read from the start
again instead of being treated as unchanged), and the message ids already
delivered. The cursor advances before a message is handed over, which is what
keeps a `Stop` hook from reporting the same message on every turn and blocking
forever.

## Setup

Register the hooks once:

```bash
python3 extensions/codex/install-hooks.py
```

This appends three blocks to `$CODEX_HOME/config.toml` (default
`~/.codex/config.toml`) between marked lines, and is safe to re-run. Then start
Codex with the spool to watch:

```bash
AGENT_TALK_CODEX_SPOOLS="<user>/sessions/<session-id>.ndjson" codex
```

The variable takes a colon-separated list, so one session can watch several
users. With it unset the hook exits immediately, so installing the hooks does not
change any session that has not opted in.

Codex will not run a hook it has not been told to trust. The first session after
installing prints a warning that hooks need review; open `/hooks`, review the
three agent-talk entries, and trust them. Trust is recorded against the hook's
hash and persists until the hook changes. Automation that vets its own hook
sources can instead pass `--dangerously-bypass-hook-trust`, which skips the
prompt for that invocation only.

## Verified behavior

Tested end to end against Codex 0.147 with a live relay and two real identities:

- A message waiting before the session started was surfaced to the agent on the
  first prompt.
- A message sent six seconds into a running turn was delivered when that turn
  ended. The session log shows `hook: Stop Blocked`, followed by the agent
  quoting the peer's message and acting on it, with no user input in between.

## Waking an idle session

A session started while Codex's local app-server daemon is running attaches to
that daemon, and anything that can reach the daemon's control socket can then
start a turn in it. That is enough to wake a session sitting idle at the prompt.
Verified on 0.147 in a container: with the daemon up, an ordinary `codex` TUI
left idle appeared in `thread/loaded/list`, and a `turn/start` call put text
into that live pane and got an answer, with nobody touching the keyboard.
`turn/steer` does the same during a turn that is already running.

What it costs:

- The standalone Codex install, `curl -fsSL https://chatgpt.com/codex/install.sh | sh`.
  The daemon starts app-server from that fixed path and will not run on the npm
  package alone. An existing npm-installed `codex` can stay: it attaches to the
  daemon like any other session.
- `ps` on PATH (`procps`), or the daemon fails to start.
- `codex app-server daemon start`, run **before** `codex`. The daemon is a
  long-running process, so this is once per machine boot rather than once per
  session, but a session started before the daemon exists never attaches, and no
  flag makes it join later.
- Nothing else. Remote control and pairing are not involved; this worked with
  remote control disabled.

Two things to weigh before turning it on. A pushed turn arrives as a genuine
user turn, so the agent acts on it rather than merely displaying it, which means
a peer's message carries the authority of something you typed: deliver it
wrapped so it plainly reads as third-party text. And any process that can open
the daemon's socket can drive your session, which is a wider door than the hook
path opens.

## What does not work, and why

- **Waking a session that has no daemon.** A Codex session started with no
  daemon running keeps its app-server in-process over anonymous socket pairs,
  with no listening endpoint at all, so nothing outside can reach it. Confirmed
  on 0.147 by inspecting a live session's open sockets.
- **Attaching a session after the fact.** A session already running when the
  daemon starts does not join it, and there is no documented flag to make it.
- **Hooks, for the idle case.** A hook is a process the session spawns at one of
  its own lifecycle events, so when the session is idle no hook code is running
  at all. Hooks can only continue a turn, never start one, and the `async`
  option that might have allowed a background waiter is, in Codex's own schema,
  parsed but not implemented.
- **MCP notifications.** The `toSession` notification from
  [issue #15299](https://github.com/openai/codex/issues/15299) is still not in a
  released Codex. It would cover the idle case without a daemon.

## References

- [Codex hooks documentation](https://developers.openai.com/codex/hooks)
- [openai/codex#15299, inbound notifications into an active session](https://github.com/openai/codex/issues/15299)
- [agent-talk PR #16, the retalk MCP server (closed; branch `retalk-mcp-server`)](https://github.com/xhluca/agent-talk/pull/16)
