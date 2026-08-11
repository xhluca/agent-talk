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
idle session directly. The installer ships a `codex-with-daemon` launcher for
exactly this; see [Waking an idle session](#waking-an-idle-session) below.
Hooks remain the default because they need nothing beyond the installer, and
the launcher stays opt-in.

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

## Waking an idle session

This part is opt-in. Everything above works with nothing more than the
installer; what follows closes the one remaining gap, the session sitting idle
at the prompt, and costs real setup to do it.

A session started while Codex's local app-server daemon is running attaches to
that daemon, and anything that can reach the daemon's control socket can then
start a turn in it. That is enough to wake a session sitting idle at the prompt.
Verified on 0.147 in a container: with the daemon up, an ordinary `codex` TUI
left idle appeared in `thread/loaded/list`, and a `turn/start` call put text
into that live pane and got an answer, with nobody touching the keyboard.
`turn/steer` does the same during a turn that is already running.

One honest caveat first: agent-talk does not place that `turn/start` call yet.
The launcher below is the setup half, making the session reachable; the
follower-side caller is planned but not built. Until it lands, this section
buys you a session that outside tooling can wake, not one that agent-talk
already wakes.

### The launcher

The installer puts a small POSIX shell launcher, `codex-with-daemon`, in
`~/.local/bin`. It runs `codex app-server daemon start` and then execs `codex`
with your arguments, so the TUI is the foreground process and signals and exit
codes pass through. Starting a daemon that is already up is a fast no-op, so
the launcher does not probe first. If the daemon cannot start, the launcher
says so on stderr and starts plain Codex anyway; that session is not wakeable
while idle, and the hooks still deliver at the next prompt or end of turn.

The launcher deliberately does not shadow `codex`. Running `codex` gives you
plain Codex, and forgetting the launcher costs only idle wake, never
correctness. The distinct name matters because Codex will not tell you when
the daemon is missing: a session started without one silently keeps its
app-server in-process and simply cannot be reached, with nothing on screen to
say so.

### What it costs

- The standalone Codex install, `curl -fsSL https://chatgpt.com/codex/install.sh | sh`.
  The daemon starts app-server from that fixed path and will not run on the npm
  package alone. An existing npm-installed `codex` can stay: it attaches to the
  daemon like any other session.
- `ps` on PATH (`procps`), or the daemon fails to start.
- The daemon must be running **before** the session starts. A session started
  earlier never attaches, and no flag makes it join later. `codex-with-daemon`
  covers this by starting the daemon on the way in.
- Nothing survives a reboot. The daemon leaves only pid files, locks, logs,
  and a socket under `$CODEX_HOME`: no systemd unit, no launchd job, no cron
  entry, no shell profile edit. Nothing respawns it if it dies, either. Using
  the launcher for every session is the simple answer; if you want the daemon
  up from boot instead, that arrangement (a user systemd unit, for example) is
  yours to make.
- Nothing else. Remote control is not needed: it is the same daemon started
  with `--remote-control` plus enrollment with OpenAI's cloud, it grants
  nothing extra locally (the wake above worked with it disabled), and routing
  messages through it would hand agent-talk plaintext to a third party, which
  is the opposite of this project's point.

### Why `daemon start` and not `bootstrap`

Codex also offers `codex app-server daemon bootstrap`. Do not use it for this.
Bootstrap starts the same daemon plus an hourly auto-updater that restarts the
app-server whenever the binary changes, and every session attached to the
daemon dies when the daemon restarts or stops. `daemon start` launches only
the server, so your sessions live until you stop it yourself. Bootstrap is
also not reboot-persistent, so it buys no durability in exchange.

### What to weigh

Two risks to accept before turning this on. First, a pushed turn arrives as a
genuine user turn, so the agent acts on it rather than merely displaying it,
which means a peer's message carries the authority of something you typed;
anything delivered this way must be wrapped so it plainly reads as third-party
text. Second, any local process that can open the daemon's socket can drive
your session, which is a wider door than the hook path opens.

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
