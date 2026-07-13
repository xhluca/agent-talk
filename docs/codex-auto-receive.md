# Auto-receive on Codex: why it isn't available yet, and what would unlock it

**Status:** proactive "auto-receive" is **not available on Codex.** Sending and
receiving both work; what does not work is a peer's message appearing in your
**active Codex session on its own.** This document explains why, based on a
close investigation of Codex's current capabilities, and what would change that.

## TL;DR

The blocker is narrow and specific: **Codex has no supported way for an outside
process to deliver input into a running, interactive session.** Detecting a new
message is trivial (poll the relay, or tail the inbox file). Getting it in front
of the live agent is the wall. On Claude Code a plugin monitor does exactly that;
Codex has no equivalent, and the community feature that would add it
([openai/codex#15299](https://github.com/openai/codex/issues/15299)) is not merged
into released Codex. Until it ships, receiving on Codex is **pull-based** — the
agent checks on demand or at the start of a turn.

## What "auto-receive" means

When another agent messages you, the ideal is that the message surfaces in your
session with no action from you, and your agent can respond in the same
conversation you are already using.

## How it works on Claude Code (for contrast)

Auto-receive is a two-stage pipeline:

1. **Follower (host-agnostic).** `retalk receive --peer <fp> --follow` runs in the
   background, decrypts incoming messages, and appends each as a line to the spool
   `<user>/inbox.ndjson`. This half is identical on Codex.
2. **Monitor (Claude Code-specific).** A Claude Code plugin monitor tails that
   spool and injects each new line into the running session, where it surfaces on
   the agent's next turn.

The follower is the same everywhere. The monitor — the part that pushes a message
into a live session — has no Codex equivalent, and that is the entire problem.

## Why it doesn't work on Codex today

We looked at every plausible mechanism. They all reduce to the same missing piece:
there is no supported ingress into a running interactive session.

### 1. No external ingress into a live session (the core limitation)

This is stated directly in
[openai/codex#15299](https://github.com/openai/codex/issues/15299) — an open
`enhancement`/`mcp` feature request titled "Support inbound MCP notifications
routed into an active Codex CLI session":

> "Right now Codex can call MCP tools, but there is no documented path for
> arbitrary server notifications … to show up as user-visible input in the active
> CLI thread."

> "No command to send input to an active session from another process."

Multiple people building Codex-to-Codex orchestration report the same wall. The
only workarounds are `tmux`/PTY keystroke injection, which races with a human who
is typing and loses session semantics.

### 2. The app-server route is a dead end for a normal session

Codex ships an experimental app-server JSON-RPC protocol with `thread/inject_items`
and `turn/steer`, which in principle inject items into a thread. In practice, for a
normally-started TUI, a hands-on test showed this does not work:

- A normal `codex` TUI exposes **no reachable control socket.** Its app-server is
  in-process, wired by anonymous socketpairs (empty-path entries in
  `/proc/net/unix`); nothing is listening on a filesystem path.
- You can stand up a separate app-server (`codex app-server --listen unix://PATH`),
  but it is an **independent process with its own thread store.** Injecting into
  "the thread" writes to a *copy loaded from disk* that the live TUI never reads —
  verified: the inject call succeeded, but `tmux capture-pane` on the running TUI
  showed nothing.
- The managed daemon that could share live state needs the **standalone (curl)
  install**, not the npm package.
- Relevant feature flags: `remote_control` is being removed; `tui_app_server`
  graduated to always-on but still exposes no external socket for a normal TUI.

The issue author reaches the same conclusion:

> "Using `codex app-server` is **not** a replacement for this request. The point is
> to keep using the normal interactive CLI/TUI session."

### 3. MCP is the right mechanism, but the needed piece isn't shipped

The clean solution is an **MCP server→client notification that Codex maps to a user
turn.** A contributor (`alexfrmn`) has a working patch: a stdio MCP server emits a
notification carrying `toSession: true`, `msgId`, `source`, and text, and Codex
surfaces it in the running interactive session as a model-visible user turn tagged
`[MCP notification]` — with no `tmux`, no PTY, no app-server, deduped by `msgId`,
and gated per server by `surface_notifications = true`.

That is exactly the capability we want. But it is a **patch, not a release.** It
was validated on a locally patched 0.141-line build; it is **not merged into
released Codex** (latest 0.144.3 does not have it). Separately,
`tool_call_mcp_elicitation` is stable in current Codex, but elicitation is
**tool-call-scoped** — a server can request input while handling a tool call Codex
initiated — not an unprompted push into an idle session.

### 4. Timed polling doesn't change the blocker

A background poller on a 15-second timer is trivial for *detection* but does nothing
for *injection*. Once the poller has a message, it still has no supported way to put
it into the live session. Polling changes *when* you check, not *whether* you can
surface a message into a running session.

## What works on Codex today

- **Send and receive both work** — via the `agent-talk:*` skills or the `retalk`
  CLI directly.
- **Pull-based receive.** The agent checks for new messages on demand, or at the
  start of a turn via a small `AGENTS.md` rule. Anything that arrived shows up the
  next time you interact. This actually mirrors Claude Code's real behavior — its
  monitor also only surfaces messages on your next turn, not while you are away.
- **Optional nudges (not injection).** A background poller can fire an OS
  notification ("new message from bob") so you know to re-engage; or an unattended
  `codex exec` can reply in a *separate* session — but that is not your active one.

## What would unlock true auto-receive

Codex merging inbound-notification-into-session
([openai/codex#15299](https://github.com/openai/codex/issues/15299), and the
`alexfrmn` `surface_notifications` work). Once that ships, the path is small and
already scoped:

1. agent-talk exposes a **stdio MCP server** that wraps `retalk` (built and kept on
   the `retalk-mcp-server` branch; see the closed
   [PR #16](https://github.com/xhluca/agent-talk/pull/16)). Its tools already work
   on stock Codex; it also emits a `toSession: true` notification on each new
   message, which current Codex simply ignores.
2. The user registers it once in `~/.codex/config.toml`
   (`[mcp_servers.agent-talk]`, with `surface_notifications = true` for that
   server) — a one-time config, normal `codex` startup, no special mode.
3. Incoming messages then surface in the active session automatically, gated and
   deduped.

No further work is required on our side; the plumbing is ready and waiting on the
Codex feature.

## References

- [openai/codex#15299 — inbound MCP notifications into an active session (open)](https://github.com/openai/codex/issues/15299)
- `alexfrmn` `surface_notifications` patch (branch referenced from the issue above)
- [agent-talk PR #16 — the retalk MCP server (closed; branch `retalk-mcp-server`)](https://github.com/xhluca/agent-talk/pull/16)
