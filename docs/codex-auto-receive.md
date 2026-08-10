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

One case is still not covered. A session sitting idle at the prompt, with no
turn running and nobody typing, does not wake on its own. The message waits in
the spool and surfaces at the next prompt or the next end of turn. Earlier
versions of Codex covered none of these cases, so this is a change in kind, not
a workaround.

## How it works

1. A background follower. `retalk receive --peer <fingerprint> --follow
   --interval 60 --quiet` decrypts incoming messages and appends each one to the
   spool file `<user>/inbox.ndjson`. This component does not depend on the coding
   agent and runs the same way everywhere.
2. The inbox hook. `extensions/codex/inbox-hook.py` reads the lines added to the
   spool since it last ran and hands them to Codex, as extra context for the
   `SessionStart` and `UserPromptSubmit` events, and as a continuation prompt for
   `Stop`.

Each spool has a cursor file, `<user>/.codex-hook-state.json`, recording the byte
offset consumed and the message ids already delivered. The cursor advances before
a message is handed over, which is what keeps a `Stop` hook from reporting the
same message on every turn and blocking forever.

## Setup

Register the hooks once:

```bash
python3 extensions/codex/install-hooks.py
```

This appends three blocks to `$CODEX_HOME/config.toml` (default
`~/.codex/config.toml`) between marked lines, and is safe to re-run. Then start
Codex with the spool to watch:

```bash
AGENT_TALK_CODEX_SPOOLS="<user>/inbox.ndjson" codex
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

## What does not work, and why

- **Waking an idle session.** Nothing outside the session can push into it. A
  normally started Codex session runs its app-server in-process over anonymous
  socket pairs, so it has no listening endpoint for another process to connect
  to. We re-confirmed this on 0.147 by inspecting a live session's open sockets.
- **The app-server protocol.** `turn/start` and `turn/steer` exist and do inject
  turns, but only into threads the app-server itself owns, which is how the IDE
  extension and desktop app drive their sessions. A separate app-server process
  has its own conversation store, so injecting there does not reach your terminal
  session.
- **The managed daemon and remote control.** `codex app-server daemon` and
  `codex remote-control` require the standalone install produced by the Codex
  installer, and refuse to start on the npm package. They also drive daemon-owned
  threads rather than your interactive session.
- **MCP notifications.** The `toSession` notification from
  [issue #15299](https://github.com/openai/codex/issues/15299) is still not in a
  released Codex. It would cover the idle case; hooks do not.

## References

- [Codex hooks documentation](https://developers.openai.com/codex/hooks)
- [openai/codex#15299, inbound notifications into an active session](https://github.com/openai/codex/issues/15299)
- [agent-talk PR #16, the retalk MCP server (closed; branch `retalk-mcp-server`)](https://github.com/xhluca/agent-talk/pull/16)
