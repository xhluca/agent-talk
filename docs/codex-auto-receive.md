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

That last case can be closed as well, at the cost of some setup. Start the
session through the `codex-with-daemon` launcher and the follower's spool
writer with `--wake-codex`, and an incoming message wakes the idle session on
its own; see [Waking an idle session](#waking-an-idle-session) below. Hooks
remain the default because they need nothing beyond the installer, and waking
stays opt-in.

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
3. Optionally, the wake caller. Started with `--wake-codex`, the spool writer
   also nudges an idle daemon-attached session after each record lands
   (`bin/codex_wake.py`), so the hook path above runs right away instead of at
   the next prompt. Details in [Waking an idle session](#waking-an-idle-session).

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
`~/.codex/config.toml`) between marked lines, and is safe to re-run. It also
copies the optional `codex-with-daemon` launcher to `~/.local/bin` (and warns
if that directory is not on your PATH); the launcher does nothing until you
choose to start Codex with it, as described in
[Waking an idle session](#waking-an-idle-session). Pass `--check` to report
what is installed without changing anything. Then start Codex with the spool
to watch:

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
- With the session started through `codex-with-daemon` and the writer running
  with `--wake-codex`: a session left fully idle, with nothing ever typed,
  woke on its own when the peer's message arrived. The pane shows the injected
  nudge turn, then the agent quoting the message verbatim and acting on it.
- With no daemon (plain `codex`) and the same `--wake-codex` writer: nothing
  was pushed, nothing was printed, and the message arrived by hook at the next
  typed prompt.

## Waking an idle session

`codex-with-daemon` is a launcher, installed to `~/.local/bin` by the
installer, that starts Codex's local app-server daemon and then runs `codex`
attached to it. Use it when you want incoming messages to reach a Codex
session that is sitting idle at the prompt; plain `codex` is fine otherwise,
and hooks still deliver at your next prompt or the end of your next turn.

Two steps turn waking on:

1. Start Codex through the launcher, with `AGENT_TALK_CODEX_SPOOLS` set as
   usual: `codex-with-daemon` in place of `codex`.
2. Start the follower's spool writer with `--wake-codex` (the receive skill
   does this when you say you use the launcher).

Both are deliberate choices. The launcher does not shadow `codex`, and the
writer never touches the daemon's socket without the flag, so a user who
adopted neither sees no change at all. Forgetting either costs only idle
wake, never delivery.

### How the wake works

When the writer appends a message to a session spool and `--wake-codex` is
set, it connects to the daemon's control socket and starts a turn in the one
loaded thread, carrying only a fixed nudge: new mail arrived, surface what
the inbox hook attaches. The message body is never pushed. An injected turn
arrives with the authority of something you typed, so peer-controlled text
must not travel that way; and because the body still comes from the hook,
there is a single delivery path with a single dedupe cursor, whether the
session was woken, prompted, or mid-turn.

The attempt is best-effort and bounded by a short deadline. No socket, no
daemon, a refused handshake, or a method error all end it silently; the
message is already in the spool and the hooks still deliver it. The writer
also does not stack nudges: while a nudged message sits unread (the hook
cursor has not moved past the point of the last nudge), further messages add
no further nudges, and a spool that is drained or rotated re-arms it. A
session with a turn already running is left alone, because the `Stop` hook
delivers the moment that turn ends; interrupting real work with `turn/steer`
to say "check your inbox" would buy nothing.

### What it costs

- The standalone Codex install
  (`curl -fsSL https://chatgpt.com/codex/install.sh | sh`); the daemon will
  not run from the npm package alone. `ps` on PATH (`procps`) as well.
- The daemon must be up before the session starts; the launcher does that.
  A session started with no daemon silently keeps its app-server in-process
  and cannot be reached, with nothing on screen to say so.
- Nothing survives a reboot, and nothing respawns a dead daemon. Using the
  launcher for every session is the simple answer; a boot-time arrangement
  (a user systemd unit, say) is yours to make.
- A daemon restart or stop kills every attached session. This is why the
  launcher uses `daemon start` and not `daemon bootstrap`: bootstrap adds an
  auto-updater that restarts the app-server whenever the binary changes,
  killing your sessions for no durability in return.
- Remote control is not needed. It is the same daemon plus enrollment with
  OpenAI's cloud, it grants nothing extra locally, and routing messages
  through it would hand agent-talk plaintext to a third party.

### What to weigh

- A pushed turn arrives as a genuine user turn, so the agent acts on it with
  the authority of something you typed. agent-talk pushes only its fixed
  nudge for exactly this reason, but the capability itself is why waking is
  opt-in.
- Any local process that can open the daemon's socket can drive your
  session, which is a wider door than the hook path opens.

### Limits, honestly

- **One session per daemon is the supported shape.** Thread ids on the
  daemon are Codex's, and nothing maps them to agent-talk sessions, so the
  writer only wakes when exactly one thread is loaded. With several attached
  sessions it stands down rather than risk injecting into the wrong one, and
  messages fall back to hook delivery.
- **The daemon keeps the environment it started with.** Attached sessions
  run their hooks inside the daemon, so `AGENT_TALK_CODEX_SPOOLS` must be
  set when the daemon first starts; the launcher passes its environment
  through, and warns when a daemon that is already running may hold a stale
  value. Changing the spool list means restarting the daemon, which ends its
  attached sessions.
- **Attached sessions work in the daemon's directory.** On 0.147 a session
  started with `--remote` takes its working directory from the daemon, not
  from where you launched the TUI. Start `codex-with-daemon` from the
  project directory the daemon should serve.
- **Hook trust must be granted for real.** For attached sessions,
  `--dangerously-bypass-hook-trust` on the TUI does not arm the hooks;
  review and trust them once under `/hooks` (press `t`).

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
