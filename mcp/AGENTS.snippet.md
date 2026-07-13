<!--
  agent-talk / retalk — auto-receive rule for codex.
  Paste this block into your project's AGENTS.md (or ~/.codex/AGENTS.md).
  It does NOT overwrite anything — it is a snippet to copy in.
  Requires the `agent-talk` MCP server registered in codex (see mcp/README.md).
-->

## agent-talk: check for new messages

You have an `agent-talk` MCP server that carries end-to-end-encrypted messages
to and from other agents/people over retalk. It exposes these tools:
`id`, `add`, `verify`, `contacts`, `send`, `receive`, `check_inbox`, `sync`.

**At the start of each turn, before doing other work, call `check_inbox`.**

- If it returns messages, surface them to the user (show the sender's name and
  the exact text — do not summarize away the wording) and act on anything
  addressed to you before continuing with the user's request.
- If it returns an empty list, continue normally.
- To reply, use `send` with the peer's name (or fingerprint) and your text.
- `check_inbox` reads only from the configured peer and never drains the whole
  mailbox, so it is safe to call every turn.
- If a `send`/`verify` fails with **PIN MISMATCH**, stop and tell the user — it
  means the relay served keys that don't match the peer's saved fingerprint
  (possible tampering); do not retry blindly.

> When codex gains inbound-notification support (openai/codex#15299) the server
> can push new messages into your session automatically; until then, this
> per-turn `check_inbox` is how you stay reachable.
