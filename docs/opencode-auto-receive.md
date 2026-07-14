# Auto-receive on opencode

## Summary

Auto-receive is supported on opencode, as on pi and unlike on Codex or
Antigravity. In this document, "auto-receive" means an incoming message from a
peer appearing in your active session without any action from you, so that the
agent can respond in the conversation you are already using.

Sending and receiving messages both work on opencode. The capability that Codex
and Antigravity lack is the delivery of an incoming message into a session that
is already running. opencode provides a supported mechanism for exactly this.
opencode runs a client/server: the interactive session is backed by a local HTTP
server, and a plugin loaded into that session receives a client already bound to
the running server. The plugin can push a message into the live session while it
is idle or streaming. That is the same role Claude Code's inbox monitor and pi's
inbox extension play. As a result, auto-receive on opencode is achievable with
opencode's shipped features and does not depend on any unreleased change.

agent-talk ships an opencode inbox plugin that does this
(`extensions/opencode/inbox-monitor.ts`). Once enabled for a session, an
incoming message from a peer surfaces in the live opencode session on its own and
triggers a turn. Enabling it is described in "Enabling auto-receive on opencode"
below.

## Background: how auto-receive works on Claude Code

On Claude Code, auto-receive uses two components:

1. A background follower. `retalk receive --peer <fingerprint> --follow` decrypts
   incoming messages and appends each one to the spool file `<user>/inbox.ndjson`.
   This component does not depend on the coding agent and runs the same way on
   opencode.
2. An inbox monitor. A Claude Code plugin reads new lines from that spool file and
   delivers them into the running session, where they appear on the agent's next
   turn. This component is specific to Claude Code.

The follower is portable. The monitor delivers a message into a running session.
opencode has an equivalent capability, which is why auto-receive is available
there.

## The capability

opencode is built as a client/server. Each interactive session is served by a
local HTTP server (the same server that `opencode serve` starts headless), and
the API exposes endpoints that admit input into a running session:

- `POST /session/{id}/prompt_async` durably admits one input and schedules the
  agent loop. This is the direct analog of pi's `sendMessage(..., { triggerTurn:
  true })`: the message becomes a real user turn and the agent responds.
- `POST /tui/append-prompt` and `POST /tui/submit-prompt` drive the prompt of the
  active terminal UI, which the opencode IDE integrations use.

A plugin does not have to discover the server URL by itself. opencode's plugin
context passes the plugin a `client` that is already connected to the running
server, plus the resolved `serverUrl` and a shell. So a plugin can call
`client.session.promptAsync(...)` against the live session directly. This works
in the standard interactive session with no special launch mode, which is why the
plugin, rather than an external process, is the right fit: it delivers into the
same session the user already has open, matching how the Claude Code monitor and
the pi extension behave.

## Approaches investigated

### An inbox plugin

An opencode plugin reproduces the Claude Code monitor and the pi extension, and
this is the mechanism agent-talk ships
(`extensions/opencode/inbox-monitor.ts`). A plugin is a JavaScript or TypeScript
module that exports a function; opencode calls it once per session with a context
object and takes the hooks it returns. On load the plugin starts watching the
follower's spool file `<user>/inbox.ndjson`. When a new line appears, it parses
the message and calls `client.session.promptAsync` for the active session, so the
message appears in the running session and the agent takes its next turn. The
plugin learns the active session id from opencode's `event` hook, which carries
the session id on session-scoped events. The follower that writes the spool is the
same portable component used on Claude Code and pi. See "Implementation" below.

### The TUI control endpoints

`POST /tui/append-prompt` followed by `POST /tui/submit-prompt` also delivers text
into the active terminal UI. This works, but it types into the user's prompt line
rather than admitting a first-class user turn, so it can collide with text the
user is composing. `prompt_async` admits the message cleanly as its own turn, so
the plugin uses that and keeps the TUI endpoints as a fallback only.

### An external process attaching to the server

An outside process can attach to a running server with `opencode attach <url>` or
a client pointed at the server's base URL, then admit a message the same way. The
obstacle is discovery: when the interactive UI starts its server on the default
port 4096 is taken, opencode silently falls back to a random port, and exporting
that port to outside processes is still an open request
([opencode#9099](https://github.com/anomalyco/opencode/issues/9099)). The in-session
plugin avoids this entirely, because opencode hands it a `client` already bound to
the correct server. That is why the plugin, not an external attacher, is the
default path for agent-talk.

### Periodic polling

A background process can poll for new messages on a fixed interval. On opencode
this is a fallback rather than a necessity: because the plugin can deliver into the
session, polling is only needed when no plugin is loaded. Where it is used, the
polling interval changes how quickly a message is detected, not whether it can be
delivered.

## Implementation

The plugin is `extensions/opencode/inbox-monitor.ts`. Its behavior:

- On load it reads the environment variable `AGENT_TALK_OPENCODE_SPOOLS`, a
  colon-separated list of absolute `inbox.ndjson` paths, and starts a watcher for
  each. If the variable is unset it registers nothing, so installing the plugin
  does not change any session that has not opted in.
- Each watcher seeks to the end of its spool at startup, so only messages that
  arrive after the session starts are surfaced. The backlog stays available
  through the receive and history skills.
- On a new spool line the plugin parses the retalk record
  (`{"id","from","name","text"}`), skips contact records, and calls
  `client.session.promptAsync` with the message as a text part, targeting the
  active session id learned from the `event` hook. If a message arrives before any
  session id is known, it is held and flushed once the id is available.
- Duplicate delivery is prevented two ways: a per-spool byte offset, so only bytes
  appended after the last read are consumed, and a set of already-delivered message
  ids.

The follower that writes the spool
(`retalk receive --peer <fingerprint> --follow`) is unchanged and portable. The
plugin only adds the delivery-into-the-session half that Claude Code's monitor and
the pi extension also provide.

## Enabling auto-receive on opencode

1. Install opencode's skills for the plugin (see the opencode Quickstart in the
   README) and place the inbox plugin where opencode loads plugins from. That is
   `~/.config/opencode/plugins/inbox-monitor.ts` (global) or
   `.opencode/plugins/inbox-monitor.ts` (project), or a reference to the npm
   package in `opencode.json` under `"plugin"`.
2. Run the agent-talk init skill and choose the `auto` delivery mode. This starts
   the `receive --follow` follower that writes `<user>/inbox.ndjson`.
3. Start opencode with `AGENT_TALK_OPENCODE_SPOOLS` set to that spool path, for
   example:

   ```bash
   AGENT_TALK_OPENCODE_SPOOLS="<user>/inbox.ndjson" opencode
   ```

   To watch more than one identity in the same session, join their spool paths
   with a colon. Because the variable is read at startup, it must be set before
   opencode launches; a session already running picks it up only after a relaunch.

With the variable set, an incoming message surfaces in the running session and the
agent takes a turn to handle it, with no manual polling and no re-running the
receive skill.

## Verification

The delivery mechanism was verified against a live opencode server (v1.17.20)
without a provider login:

- A headless server admitted an injected message through
  `POST /session/{id}/prompt_async`. Reading the session back showed the injected
  text as a first-class `user` message and a scheduled `assistant` turn, which is
  exactly what the plugin relies on: the message became a real turn in the running
  session rather than only being logged.
- The `prompt_async`, `tui/append-prompt`, `tui/submit-prompt`, and `event`
  surfaces used by the plugin are present in the server's OpenAPI document and in
  the `@opencode-ai/sdk` and `@opencode-ai/plugin` type definitions shipped with
  the release.

The final leg, the agent generating a reply to the injected message, needs an
authenticated model provider, which is the user's credential. That leg was not
exercised in this environment; everything up to and including admission of the
message as a user turn was.

## References

- [opencode server API and SDK](https://opencode.ai/docs/server/), including
  `POST /session/{id}/prompt_async` and the `/tui/append-prompt` and
  `/tui/submit-prompt` control endpoints
- [opencode plugins](https://opencode.ai/docs/plugins/): a plugin receives a
  context with `client`, `serverUrl`, and `$`, and returns hooks including `event`
- [opencode skills](https://opencode.ai/docs/skills/): `SKILL.md` discovery paths
- [opencode#9099, export the actual server URL as an environment variable](https://github.com/anomalyco/opencode/issues/9099),
  the reason an external attacher cannot reliably find the interactive session's
  port and the plugin's bound `client` is used instead
- [Auto-receive on pi](pi-auto-receive.md), the contrasting host where the same
  in-session delivery is available
- [Auto-receive on Codex](codex-auto-receive.md), the contrasting host where the
  delivery mechanism does not yet exist
