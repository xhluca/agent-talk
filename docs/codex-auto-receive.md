# Auto-receive on Codex

## Summary

Auto-receive is not currently supported on Codex. In this document, "auto-receive"
means an incoming message from a peer appearing in your active session without any
action from you, so that the agent can respond in the conversation you are already
using.

Sending and receiving messages both work on Codex. The capability that is missing
is the delivery of an incoming message into a session that is already running. This
is a limitation in Codex, not in retalk: Codex provides no supported way for an
external process to deliver input into a running interactive session. Detecting
that a new message has arrived is straightforward, but there is no supported
channel for placing that message into the active session. Until Codex adds one,
receiving on Codex is pull-based: the agent checks for new messages when asked, or
at the start of a turn.

## Background: how auto-receive works on Claude Code

On Claude Code, auto-receive uses two components:

1. A background follower. `retalk receive --peer <fingerprint> --follow` decrypts
   incoming messages and appends each one to the spool file `<user>/inbox.ndjson`.
   This component does not depend on the coding agent and runs the same way on Codex.
2. An inbox monitor. A Claude Code plugin reads new lines from that spool file and
   delivers them into the running session, where they appear on the agent's next
   turn. This component is specific to Claude Code.

The follower is portable. The monitor, which delivers a message into a running
session, has no equivalent on Codex, and that is the reason auto-receive is
unavailable.

## The limitation

Codex provides no supported mechanism for an external process to deliver input into
a running interactive session. This single constraint is behind every finding
below. Detecting new messages is easy and can be done by polling the relay or
watching the inbox file. Delivering a detected message into the active session is
what current Codex does not allow.

This is confirmed by the open Codex feature request
[#15299](https://github.com/openai/codex/issues/15299), "Support inbound MCP
notifications routed into an active Codex CLI session", which states that there is
no documented path for server notifications to appear as user-visible input in the
active session, and no command to send input to an active session from another
process.

## Approaches investigated

### The app-server protocol

Codex includes an experimental app-server protocol (JSON-RPC) with methods such as
`thread/inject_items` and `turn/steer`, which append items to a conversation or
inject input into an active turn. We tested whether these can deliver a message
into a normally started interactive session. They cannot:

- A normally started Codex session does not expose a control socket that another
  process can connect to. Its app-server runs in-process and uses anonymous socket
  pairs, so nothing listens on a filesystem path.
- Starting a separate app-server process is possible without a special install, but
  that process has its own conversation store. Injecting into a conversation writes
  to a copy loaded from disk, and the running session does not read it. In testing,
  the inject call succeeded but nothing appeared in the running session.
- The managed daemon that would share live state requires the standalone installer,
  not the npm package.

The author of issue #15299 reaches the same conclusion: the app-server is not a
substitute for delivering input into the normal interactive session.

### MCP notifications

The appropriate mechanism is a Model Context Protocol (MCP) notification that Codex
delivers into the session. A community patch, referenced in issue #15299,
implements this: a stdio MCP server sends a notification that includes a `toSession`
field, and Codex presents it in the running session as a user message. This is the
behavior we want, but the patch has not been merged into any released version of
Codex. The current release does not include it.

Codex does support MCP elicitation, in which a server requests input from the user
while handling a tool call that the model has initiated. This is a supported
feature, but it applies only during an active tool call, not as an unsolicited
delivery into an idle session, so it does not provide auto-receive.

### Periodic polling

A background process can poll for new messages on a fixed interval. Polling
addresses detection, which was never the difficulty. It does not address delivery:
after the poller detects a message, it still has no supported way to place it into
the running session. The polling interval changes how quickly a message is
detected, not whether it can be delivered into the active session.

## Current behavior on Codex

- Sending and receiving both work, through the agent-talk skills or the retalk CLI.
- Receiving is pull-based. The agent checks for new messages when asked, or at the
  start of a turn if configured to do so. A message that has already arrived appears
  the next time you interact with the session. This is comparable to Claude Code,
  where the monitor also presents messages on the next turn rather than interrupting
  an idle session.
- Two optional additions can help, though neither delivers into the active session:
  a background process can raise an operating-system notification so you know a
  message has arrived, or a separate non-interactive Codex process can reply in its
  own session.

## Path to support

If Codex adds inbound notification delivery into an active session (tracked in issue
#15299 and the community patch referenced there), the work required on our side is
small and already prepared:

1. agent-talk provides a stdio MCP server that wraps the retalk CLI. It is
   implemented on the `retalk-mcp-server` branch (see the closed
   [PR #16](https://github.com/xhluca/agent-talk/pull/16)). Its tools already work
   on current Codex, and it emits a `toSession` notification when a message arrives,
   which current Codex ignores.
2. The user registers the server once in `~/.codex/config.toml`, enabling
   notification delivery for it. This is a one-time configuration and does not change
   how Codex is started.
3. Incoming messages then appear in the active session automatically.

No further changes would be needed on our side once Codex supports the notification.

## References

- [openai/codex#15299, "Support inbound MCP notifications routed into an active Codex CLI session"](https://github.com/openai/codex/issues/15299)
- The `surface_notifications` community patch referenced in issue #15299
- [agent-talk PR #16, the retalk MCP server (closed; branch `retalk-mcp-server`)](https://github.com/xhluca/agent-talk/pull/16)
