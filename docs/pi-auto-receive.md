# Auto-receive on pi

## Summary

Auto-receive is supported on pi, unlike on Codex. In this document, "auto-receive"
means an incoming message from a peer appearing in your active session without any
action from you, so that the agent can respond in the conversation you are already
using.

Sending and receiving messages both work on pi. The capability that Codex lacks is
the delivery of an incoming message into a session that is already running. pi
provides a supported mechanism for exactly this. A pi extension runs inside the
normal interactive session and can push a user message into it while it is idle or
streaming. That is the same role Claude Code's inbox monitor plays. As a result,
auto-receive on pi is achievable with pi's shipped features and does not depend on
any unreleased change.

agent-talk does not ship the pi extension yet, so today receiving on pi is
pull-based: the agent checks for new messages when asked, or at the start of a
turn. The section "Path to support" below describes the small piece of work that
turns on live delivery.

## Background: how auto-receive works on Claude Code

On Claude Code, auto-receive uses two components:

1. A background follower. `retalk receive --peer <fingerprint> --follow` decrypts
   incoming messages and appends each one to the spool file `<user>/inbox.ndjson`.
   This component does not depend on the coding agent and runs the same way on pi.
2. An inbox monitor. A Claude Code plugin reads new lines from that spool file and
   delivers them into the running session, where they appear on the agent's next
   turn. This component is specific to Claude Code.

The follower is portable. The monitor delivers a message into a running session.
pi has an equivalent capability, which is why auto-receive is available there.

## The capability

pi lets an external trigger deliver input into a running interactive session. Two
mechanisms provide this, both documented and shipped:

1. Extensions. A pi extension is a TypeScript module loaded into the normal
   interactive session. It can watch a file or run any background task, then call
   `pi.sendMessage(..., { triggerTurn: true })` or `pi.sendUserMessage(...)` to
   place a message into the session and trigger a turn. pi ships an example,
   `file-trigger.ts`, that watches a file and injects its contents into the
   conversation for exactly this purpose. This works in the standard interactive
   session with no special launch mode.
2. RPC mode. Started with `pi --mode rpc`, pi reads JSON commands on stdin. A
   controlling process sends `{"type": "prompt", ...}` or `{"type": "steer", ...}`
   to deliver a message into the running session. This requires launching pi in RPC
   mode and embedding it in a host process, so it fits programmatic integrations
   rather than a session a person is already using in a terminal.

For agent-talk the extension is the right fit, because it delivers into the same
interactive session the user already has open, matching how the Claude Code monitor
behaves.

## Approaches investigated

### An inbox extension

A pi extension can reproduce the Claude Code monitor. On `session_start` it watches
the follower's spool file `<user>/inbox.ndjson`. When a new line appears, it decodes
the message and calls `pi.sendMessage` with `triggerTurn: true`, so the message
appears in the running session and the agent takes its next turn. The follower that
writes the spool is the same portable component used on Claude Code. This is the
intended path and is described under "Path to support".

### RPC mode

RPC mode delivers input into a running session through stdin commands. It works, but
it requires starting pi as `pi --mode rpc` under a controlling process. That changes
how pi is launched and does not target a session a user already has open
interactively, so it is not the default path for agent-talk. It remains available
for programmatic hosts that embed pi.

### Periodic polling

A background process can poll for new messages on a fixed interval. On pi this is a
fallback rather than a necessity: because the extension path can deliver into the
session, polling is only needed when no extension is loaded. Where it is used, the
polling interval changes how quickly a message is detected, not whether it can be
delivered.

## Current behavior on pi

- Sending and receiving both work, through the agent-talk skills or the retalk CLI.
- Receiving is pull-based today, because agent-talk does not yet ship the pi inbox
  extension. The agent checks for new messages when asked, or at the start of a
  turn if configured to do so. A message that has already arrived appears the next
  time you interact with the session.
- Live delivery is available in principle now, through a pi extension, and becomes
  the default once agent-talk ships that extension.

## Path to support

pi already provides the delivery mechanism, so enabling auto-receive is work on our
side only, and it is small:

1. Ship a pi extension that mirrors the Claude Code inbox monitor. It watches the
   follower's spool file `<user>/inbox.ndjson` and calls `pi.sendMessage` with
   `triggerTurn: true` for each new message. The follower that writes the spool is
   already portable and unchanged.
2. Package the extension with the plugin so pi discovers it, the same way pi already
   discovers the skills in `skills/`.
3. Incoming messages then appear in the active session automatically.

No change to pi is required. Unlike Codex, there is no dependency on an unshipped
upstream feature.

## References

- [pi extensions: `pi.sendMessage` and `pi.sendUserMessage`](https://pi.dev)
- The `file-trigger.ts` example shipped with pi, which watches a file and injects
  its contents into the running session
- [pi RPC mode: the `prompt` and `steer` commands](https://pi.dev)
- [Auto-receive on Codex](codex-auto-receive.md), the contrasting case where the
  delivery mechanism does not yet exist
