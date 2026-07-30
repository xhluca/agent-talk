# Auto-receive on GitHub Copilot CLI

## Summary

Auto-receive is not currently supported on the interactive GitHub Copilot CLI (the
standalone `copilot` command). In this document, "auto-receive" means an incoming
message from a peer appearing in your active session without any action from you, so
that the agent can respond in the conversation you are already using.

Sending and receiving messages both work on Copilot CLI. The capability that is
missing is the delivery of an incoming message into the interactive session that is
already running. This is a limitation in the interactive Copilot CLI, not in retalk:
Copilot CLI provides no supported way for an unrelated background process on the same
machine to deliver input into a running interactive session. Detecting that a new
message has arrived is straightforward, but there is no supported channel for placing
that message into the active interactive session. Until Copilot CLI adds one,
receiving on Copilot CLI is pull-based: the agent checks for new messages when asked,
or at the start of a turn.

There is a supported programmatic path (the Agent Client Protocol server) that can
inject a turn into a session, but it applies to a session that a client owns and
drives, not to the user's interactive terminal session. See "Path to support" below.

## Background: how auto-receive works on Claude Code

On Claude Code, auto-receive uses two components:

1. A background follower. `retalk receive --peer <fingerprint> --follow --interval 60 --quiet` decrypts
   incoming messages and appends each one to the spool file `<user>/inbox.ndjson`.
   This component does not depend on the coding agent and runs the same way on
   Copilot CLI.
2. An inbox monitor. A Claude Code plugin reads new lines from that spool file and
   delivers them into the running session, where they appear on the agent's next
   turn. This component is specific to Claude Code.

The follower is portable. The monitor, which delivers a message into a running
session, has no equivalent for the interactive Copilot CLI, and that is the reason
auto-receive is unavailable there.

## The limitation

The interactive Copilot CLI provides no supported mechanism for an unrelated
background process to deliver input into a running interactive session. This single
constraint is behind every finding below. Detecting new messages is easy and can be
done by polling the relay or watching the inbox file. Delivering a detected message
into the active interactive session is what the current interactive Copilot CLI does
not allow.

## Approaches investigated

### Hooks

Copilot CLI ships a hooks system with lifecycle events (`sessionStart`,
`userPromptSubmitted`, `preToolUse`, `postToolUse`, `agentStop`, `notification`,
`sessionEnd`, and others). Two of these can add text to a conversation, but neither
gives an outside process a way to wake an idle session with a peer's message:

- The `sessionStart` hook can return `additionalContext`, which is injected into the
  conversation, but only once, at the start of the session. It does not fire again
  for a message that arrives later, so it cannot surface an incoming message during a
  live session.
- The `notification` hook fires when the CLI itself emits a system notification, and
  its output can be prepended to the session as a user message. This is driven by the
  CLI's own internal notification events, not by an external process. There is no
  supported way for an outside watcher, such as the retalk follower, to emit a
  notification into a running session, so this is not a general injection channel.

The broader request to inject arbitrary hook command output into the conversation
context was raised in Copilot CLI issue
[#1139](https://github.com/github/copilot-cli/issues/1139); the part that shipped is
the `sessionStart` `additionalContext` path above, which is session-start only.

### The Agent Client Protocol (ACP) server

Copilot CLI can run as an Agent Client Protocol server (`copilot --acp`, over stdio
by default or a TCP port). An ACP client creates a session and drives user turns into
it with `session/prompt`, and the agent responds. This is a genuine client/server
interface, and an external process can deliver a turn through it. The obstacle for
auto-receive is that the ACP server serves a session the client itself creates and
owns; it is not the user's interactive terminal session. Injecting a turn over ACP
therefore reaches an agent process the injector started, not the `copilot` session
the user is typing in. This is the same shape as the Codex app-server limitation:
the programmatic surface drives its own conversation, not the running interactive
one.

### The Copilot SDK and the headless server

The Copilot SDK connects to a headless Copilot server (`copilot --headless --port
<port>`) and can steer a message into a session with `session.send({ prompt, mode:
"immediate" })` or queue one with `mode: "enqueue"`. As with ACP, this drives a
session the SDK client owns through the headless server, not the user's interactive
terminal session, so it does not deliver into the session the user already has open.

### Remote control from GitHub web and mobile

Copilot CLI has a remote-control feature (`--remote`, `--connect`) that lets you
drive a session from GitHub's web and mobile clients. This routes through GitHub's
own authenticated control plane rather than a general local channel that an arbitrary
process on the same machine could use, so it is not a mechanism a local follower can
use to inject a peer's message.

### Periodic polling

A background process can poll for new messages on a fixed interval. Polling addresses
detection, which was never the difficulty. It does not address delivery: after the
poller detects a message, it still has no supported way to place it into the running
interactive session. The polling interval changes how quickly a message is detected,
not whether it can be delivered into the active session.

## Current behavior on Copilot CLI

- Sending and receiving both work, through the agent-talk skills or the retalk CLI.
- Receiving is pull-based. The agent checks for new messages when asked, or at the
  start of a turn if configured to do so. A message that has already arrived appears
  the next time you interact with the session. This is comparable to Claude Code,
  where the monitor also presents messages on the next turn rather than interrupting
  an idle session.
- A background process can raise an operating-system notification so you know a
  message has arrived, or a separate non-interactive `copilot -p "..."` process can
  reply in its own session, though neither delivers into the interactive session.

## Path to support

If Copilot CLI adds a supported way for an external process to deliver input into a
running interactive session, the work on our side is small and already prepared: the
portable follower (`retalk receive --peer <fingerprint> --follow --interval 60 --quiet`) already writes the
spool that Claude Code, pi, and opencode read, so only the delivery half would need a
Copilot-specific adapter. The most likely shapes are:

1. A way to attach an ACP or headless client to the user's interactive session,
   rather than only to a client-created one, so a turn injected over `session/prompt`
   or `session.send` reaches the session the user has open.
2. A hook or notification channel that an external process can trigger, so the
   follower could deliver an incoming message as a prepended user message on arrival.

Either would let the follower push straight into the live session, matching how the
Claude Code monitor and the pi and opencode inbox plugins already work.

## References

- [Adding agent skills for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)
- [Using hooks with GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-hooks)
  and the [Copilot hooks reference](https://docs.github.com/en/copilot/reference/hooks-reference)
- [github/copilot-cli#1139, request to inject hook command output into the LLM context](https://github.com/github/copilot-cli/issues/1139)
- [ACP support in Copilot CLI (public preview)](https://github.blog/changelog/2026-01-28-acp-support-in-copilot-cli-is-now-in-public-preview/)
- [Copilot SDK steering and queueing](https://docs.github.com/en/copilot/how-tos/copilot-sdk/use-copilot-sdk/steering-and-queueing)
- [Auto-receive on Codex](codex-auto-receive.md), the contrasting host with the same
  interactive-session limitation
- [Auto-receive on opencode](opencode-auto-receive.md), a host where in-session
  delivery is available
