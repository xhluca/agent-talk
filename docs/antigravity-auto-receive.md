# Auto-receive on Antigravity

## Summary

Auto-receive is not currently supported on the Antigravity CLI (`agy`). In this
document, "auto-receive" means an incoming message from a peer appearing in your
active session without any action from you, so that the agent can respond in the
conversation you are already using.

Sending and receiving messages both work on Antigravity. The capability that is
missing is the delivery of an incoming message into a session that is already
running. This is a limitation in the Antigravity CLI, not in retalk: the CLI
provides no supported way for an external process to deliver input into a running
interactive session. Detecting that a new message has arrived is straightforward,
but there is no supported channel for placing that message into the active
session. Until Antigravity adds one, receiving on Antigravity is pull-based: the
agent checks for new messages when asked, or at the start of a turn.

## Background: how auto-receive works on Claude Code

On Claude Code, auto-receive uses two components:

1. A background follower. `retalk receive --peer <fingerprint> --follow` decrypts
   incoming messages and appends each one to the spool file `<user>/inbox.ndjson`.
   This component does not depend on the coding agent and runs the same way on
   Antigravity.
2. An inbox monitor. A Claude Code plugin reads new lines from that spool file and
   delivers them into the running session, where they appear on the agent's next
   turn. This component is specific to Claude Code.

The follower is portable. The monitor, which delivers a message into a running
session, has no equivalent on Antigravity, and that is the reason auto-receive is
unavailable.

## The limitation

The Antigravity CLI provides no supported mechanism for an external process to
deliver input into a running interactive session. This single constraint is behind
every finding below. Detecting new messages is easy and can be done by polling the
relay or watching the inbox file. Delivering a detected message into the active
session is what the current CLI does not allow.

The CLI exposes exactly three ways to run: the default interactive TUI, an
interactive prompt mode (`-i` / `--prompt-interactive`), and a one-shot print mode
(`-p` / `--print`). None of them accept input from another process while a session
is live. This is confirmed by the open feature request
[antigravity-cli#31](https://github.com/google-antigravity/antigravity-cli/issues/31),
"add ACP (Agent Client Protocol) stdio JSON-RPC mode", which asks for exactly the
missing capability and states that none of the current modes can be driven
programmatically by an external orchestrator: there is no supported way to inject
input into a running session, receive streaming events from it, or steer it from
another process.

## Approaches investigated

### An external control protocol (ACP / JSON-RPC over stdio)

Peer CLIs (`gemini-cli`, `claude`, `cursor-agent`) can run as a JSON-RPC agent
server over stdio, which lets an external orchestrator drive a session and push
items into it. The Antigravity CLI does not implement this mode. It is the subject
of the open request above and is not present in any released version. Without it,
there is no protocol endpoint for another process to connect to and no way to hand
a message to a live session.

### The CLI as an MCP server

The Antigravity CLI can be wrapped so that the agent starts a job and the wrapper
streams progress back as MCP notifications (`notifications/message`,
`notifications/progress`). This flow runs the other direction from what we need:
the notifications travel from a job the agent itself launched back to the model
host, during a tool call the model already initiated. They are not an unsolicited
delivery from an outside process into an idle interactive session, so they do not
provide auto-receive.

### Terminal keyboard automation

A third-party approach drives a running session by simulating keystrokes at the
operating-system level (focus the terminal, clear the input, type the text, press
Enter). This is not a supported interface. It depends on window focus and terminal
state, it is specific to each platform and terminal, and it can collide with
whatever the user is doing. We do not build on it.

### Periodic polling

A background process can poll for new messages on a fixed interval. Polling
addresses detection, which was never the difficulty. It does not address delivery:
after the poller detects a message, it still has no supported way to place it into
the running session. The polling interval changes how quickly a message is
detected, not whether it can be delivered into the active session.

## Current behavior on Antigravity

- Sending and receiving both work, through the agent-talk skills or the retalk CLI.
- Receiving is pull-based. The agent checks for new messages when asked, or at the
  start of a turn if configured to do so. A message that has already arrived appears
  the next time you interact with the session. This is comparable to Claude Code,
  where the monitor also presents messages on the next turn rather than interrupting
  an idle session.
- Two optional additions can help, though neither delivers into the active session:
  a background process can raise an operating-system notification so you know a
  message has arrived, or a separate print-mode (`agy -p`) run can produce a reply
  in its own one-shot invocation.

## Path to support

If the Antigravity CLI adds a supported way to deliver input into an active session,
the work required on our side is small and already prepared:

1. agent-talk provides a stdio MCP server that wraps the retalk CLI. It is
   implemented on the `retalk-mcp-server` branch (see the closed
   [PR #16](https://github.com/xhluca/agent-talk/pull/16)). Its tools work on any
   host that speaks MCP, and it emits a notification when a message arrives.
2. Once the CLI exposes an external control protocol (the ACP mode tracked in
   [antigravity-cli#31](https://github.com/google-antigravity/antigravity-cli/issues/31))
   or routes an inbound notification into the active session, the follower's spool
   can be surfaced the same way the Claude Code monitor does today.
3. Incoming messages then appear in the active session automatically.

No further changes would be needed on our side once the CLI supports the delivery.

## References

- [google-antigravity/antigravity-cli#31, "Feature request: add ACP (Agent Client Protocol) stdio JSON-RPC mode"](https://github.com/google-antigravity/antigravity-cli/issues/31)
- [agent-talk PR #16, the retalk MCP server (closed; branch `retalk-mcp-server`)](https://github.com/xhluca/agent-talk/pull/16)
