# retalk MCP server (`agent-talk`)

A **stdio MCP server** that wraps the [`retalk`](https://github.com/xhluca/retalk)
CLI, so **codex** (and any MCP client) can do agent-talk — send and receive
end-to-end-encrypted messages — over **structured tools** instead of shell
commands.

It shells out to `retalk` (which already prints JSON / NDJSON) and returns the
parsed results. It **does not re-implement retalk's crypto**, and it **does not
patch codex**. This is the codex integration path; on Claude Code you already
have the plugin + skills.

- Server: [`retalk_mcp_server.py`](retalk_mcp_server.py) (Python, stdio)
- Agent rule to paste into your `AGENTS.md`: [`AGENTS.snippet.md`](AGENTS.snippet.md)

## Why an MCP server (and what "auto-receive" means on codex)

On Claude Code, a background follower (`retalk receive --follow`) writes new
messages to a spool and a plugin *monitor* pushes each one into the running
session. **Codex has no equivalent push today** — see the design note in
`.claude/notes/codex-auto-receive-design.md`. So auto-receive on codex is
**pull-based today**, with a **forward-compatible push** half that lights up when
codex ships session-ingress for MCP notifications
([openai/codex#15299](https://github.com/openai/codex/issues/15299)):

1. **Pull (works on stock codex now).** The `receive` / `check_inbox` tools let
   the agent fetch new mail, and the `AGENTS.snippet.md` rule tells it to check
   at the start of a turn. This mirrors Claude's "surfaces on your next turn"
   behavior.
2. **Push (forward-compatible, no patch).** With `RETALK_WATCH_PEER` set, the
   server runs `retalk receive --peer <fp> --follow` in the background and emits
   an MCP notification for each new message, shaped like the alexfrmn
   `surface_notifications` design (`notifications/message` with
   `toSession: true`, `msgId`, `source`, `text`). **On current codex (0.144.x)
   this is inert** — a normal, ignorable notification, *not* an error (verified).
   It activates only if codex maps `toSession` MCP notifications into the active
   session (#15299 / the alexfrmn branch). Deduped by `msgId`; opt-in; off by
   default.

## Requirements

- `retalk` on `PATH` (`pip install retalk` / `uv pip install retalk`), configured
  with an identity (`retalk init ...`).
- The `mcp` Python package (`pip install mcp`). The server uses only its stdlib +
  `mcp`.
- A retalk relay URL (an existing one, or your own — see the `relay` skill).

## Configuration (environment)

The server acts as **one** retalk identity, chosen once at startup, so tool calls
never carry secrets. Identity selection (first match wins):

| Env var | Meaning |
| --- | --- |
| `RETALK_DIR` | an explicit identity directory → `retalk --dir DIR` |
| `RETALK_USER` | a named identity in `~/.retalk/` → `retalk --user NAME` |

Optional (all forwarded to `retalk` when set):

| Env var | Meaning |
| --- | --- |
| `RETALK_PASSPHRASE` | unlocks an encrypted identity (passed via the child env, **never** on argv, so it is not visible in the process list) |
| `RETALK_RELAY` | relay URL override |
| `RETALK_API_KEY` | relay access key, if the relay requires one |
| `RETALK_HOME` | where named identities live (default `~/.retalk`) |
| `RETALK_WATCH_PEER` | **opt-in push**: a peer fingerprint to `--follow`; also the default sender for `receive` / `check_inbox` when no `peer` is given |
| `RETALK_RECEIVE_FROM` | default sender for `receive` / `check_inbox` (if you want a default without enabling push) |
| `RETALK_BIN` | path to the `retalk` binary if it is not on `PATH` |

## Tools

Names mirror the `retalk` subcommands. All return retalk's machine-readable
output; `PIN MISMATCH` and relay-unreachable failures come back as clean tool
errors.

| Tool | Args | Returns |
| --- | --- | --- |
| `id` | — | `{fingerprint, identity_key, name, ...}` — your own address |
| `add` | `fingerprint`, `name?`, `verify?` | `{added, verified, name?}` |
| `verify` | `peer` | `{verified}` (or a `PIN MISMATCH` error) |
| `contacts` | — | `[{name, fingerprint, verified, ...}, ...]` |
| `send` | `peer`, `text` | `{id, to}` |
| `receive` | `peer?` | `[{id, from, name, text}, ...]` (never `--all`; defaults to the configured peer) |
| `check_inbox` | — | same as `receive` with no `peer` — a convenience for "any new mail?" |
| `sync` | — | `{republished, replenished, fallback_rotated, resent, ...}` |

`receive` never drains the whole mailbox (no `--all`) — it only ever reads from a
specific saved peer, matching the agent-talk safety rule.

## Register with codex

One-time config, normal `codex` startup — no special mode.

### `codex mcp add`

```bash
codex mcp add agent-talk \
  --env RETALK_DIR=$HOME/.retalk/alice \
  --env RETALK_RELAY=https://retalk-relay.mcgill-nlp.org \
  -- python /ABSOLUTE/PATH/TO/agent-talk/mcp/retalk_mcp_server.py
```

(Use `RETALK_USER=alice` instead of `RETALK_DIR` if you prefer a named identity.
Add `--env RETALK_PASSPHRASE=…` if the identity is encrypted, and
`--env RETALK_WATCH_PEER=<peer-fp>` to enable the forward-compat push half.)

### `~/.codex/config.toml`

```toml
[mcp_servers.agent-talk]
command = "python"
args = ["/ABSOLUTE/PATH/TO/agent-talk/mcp/retalk_mcp_server.py"]
env = { RETALK_DIR = "/home/you/.retalk/alice", RETALK_RELAY = "https://retalk-relay.mcgill-nlp.org" }

# Forward-compatible push (opt-in). Harmless / inert on codex 0.144.x; activates
# if codex ships session-ingress for MCP notifications (openai/codex#15299).
# surface_notifications = true
```

Then confirm codex sees it:

```bash
codex mcp list          # should list `agent-talk`
```

## Auto-receive setup

- **Pull (works now):** paste [`AGENTS.snippet.md`](AGENTS.snippet.md) into your
  project (or `~/.codex/`) `AGENTS.md`. It tells the agent to call `check_inbox`
  at the start of a turn and surface anything new.
- **Push (forward-compatible):** set `RETALK_WATCH_PEER=<peer-fp>` in the server
  env (and, once codex supports it, `surface_notifications = true` for this
  server). Until codex ships #15299 this emits inert notifications — safe to
  leave on.

## Notes

- Throwaway/test identities only for demos; never print secrets.
- This server does not modify `retalk` or `codex`.
- Bundling the server into the codex plugin manifest can be a follow-up; a
  standalone server + this config is enough.
