# Auto-receive on pi

## Summary

Auto-receive is supported on pi, unlike on Codex. In this document, "auto-receive"
means an incoming message from a peer appearing in your active session without any
action from you, so that the agent can respond in the conversation you are already
using.

Sending and receiving messages both work on pi. The capability that Codex lacks is
the delivery of an incoming message into a session that is already running. pi
provides a supported mechanism for exactly this. A pi extension runs inside the
normal interactive session and can push a message into it while it is idle or
streaming. That is the same role Claude Code's inbox monitor plays. As a result,
auto-receive on pi is achievable with pi's shipped features and does not depend on
any unreleased change.

agent-talk now ships a pi inbox extension that does this. It is included with the
plugin package and, once enabled for a session, an incoming message from a peer
surfaces in the live pi session on its own and triggers a turn. Enabling it is
described in "Enabling auto-receive on pi" below, and the behavior was verified
end to end between two live pi sessions (see "Verification").

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

A pi extension reproduces the Claude Code monitor, and this is the mechanism
agent-talk ships (`extensions/inbox-monitor.ts`). On `session_start` it watches the
follower's spool file `<user>/inbox.ndjson`. When a new line appears, it parses the
message and calls `pi.sendMessage` with `triggerTurn: true`, so the message appears
in the running session and the agent takes its next turn. The follower that writes
the spool is the same portable component used on Claude Code. See "Implementation"
below.

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

## Implementation

The extension is `extensions/inbox-monitor.ts`, shipped in the plugin's `pi`
manifest under `extensions`, so pi loads it the same way it loads the skills in
`skills/`. Its behavior:

- On `session_start` it reads the environment variable `AGENT_TALK_PI_SPOOLS`, a
  colon-separated list of absolute `inbox.ndjson` paths, and starts a watcher for
  each. If the variable is unset it registers nothing, so installing the plugin
  does not change any session that has not opted in.
- Each watcher seeks to the end of its spool at startup, so only messages that
  arrive after the session starts are surfaced. The backlog stays available through
  the receive and history skills.
- On a new spool line the extension parses the retalk record
  (`{"id","from","name","text"}`), skips contact records, and calls
  `pi.sendMessage` with `triggerTurn: true`. If pi is idle this triggers a turn
  immediately; if it is streaming, the message is queued and delivered after the
  current assistant turn finishes its tool calls.
- Duplicate delivery is prevented two ways: a per-spool byte offset, so only bytes
  appended after the last read are consumed, and a set of already-delivered message
  ids.
- Watchers are closed on `session_shutdown`.

The follower that writes the spool
(`retalk receive --peer <fingerprint> --follow`) is unchanged and portable. The
extension only adds the delivery-into-the-session half that Claude Code's monitor
also provides.

## Enabling auto-receive on pi

1. Install the plugin so pi has the extension: `pi install git:github.com/xhluca/agent-talk`.
2. Run the agent-talk init skill and choose the `auto` delivery mode. This starts
   the `receive --follow` follower that writes `<user>/inbox.ndjson`.
3. Start pi with `AGENT_TALK_PI_SPOOLS` set to that spool path, for example:

   ```bash
   AGENT_TALK_PI_SPOOLS="<user>/inbox.ndjson" pi
   ```

   To watch more than one identity in the same session, join their spool paths with
   a colon. Because the variable is read at startup, it must be set before pi
   launches; a session already running picks it up only after a relaunch.

With the variable set, an incoming message surfaces in the running session and the
agent takes a turn to handle it, with no manual polling and no re-running the
receive skill.

## Verification

The round trip was tested between two live pi sessions on the public relay, each
running the extension against its own spool with a `receive --follow` follower:

- Alice sent an encrypted message with `retalk send`. Bob's follower decrypted it
  into his spool, the extension injected it into Bob's running pi session, and Bob's
  session emitted `turn_start` and a `custom` message with `customType`
  `agent-talk-inbox` carrying Alice's exact text, about two to three seconds after
  the send. No polling and no receive-skill call.
- Bob's session answered the injected question ("What is 17 plus 25?") with `42`,
  confirming the message reached the agent as real input rather than only being
  logged.
- Bob's reply was sent back with `retalk send`, and Alice's live pi session surfaced
  it the same way, confirming the behavior in both directions.

## References

- [pi extensions: `pi.sendMessage` and `pi.sendUserMessage`](https://pi.dev)
- The `file-trigger.ts` example shipped with pi, which watches a file and injects
  its contents into the running session
- [pi RPC mode: the `prompt` and `steer` commands](https://pi.dev)
- [Auto-receive on Codex](codex-auto-receive.md), the contrasting case where the
  delivery mechanism does not yet exist
