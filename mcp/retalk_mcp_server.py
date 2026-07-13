#!/usr/bin/env python3
"""retalk MCP server — a stdio MCP server that wraps the `retalk` CLI.

Lets codex (and any MCP client) do agent-talk over structured tools instead of
shell commands. It shells out to `retalk` (which prints JSON / NDJSON) and
returns the parsed results; it never re-implements retalk's crypto.

Identity
--------
The server always acts as ONE retalk identity, chosen once at startup (so tool
calls never have to pass secrets). Selection, first match wins:

  * RETALK_DIR            an explicit identity directory  -> `retalk --dir DIR`
  * RETALK_USER           a named identity in ~/.retalk/  -> `retalk --user NAME`

Optional environment (all forwarded to retalk if set):

  * RETALK_PASSPHRASE     unlocks an encrypted identity (never printed)
  * RETALK_RELAY          relay URL override
  * RETALK_API_KEY        relay access key, if the relay requires one
  * RETALK_HOME           where named identities live (default ~/.retalk)

Tools (names mirror the retalk subcommands)
-------------------------------------------
  id                      -> {fingerprint, identity_key, name, ...}
  add(fingerprint,name?,verify?)
  verify(peer)
  contacts()              -> [ {name,fingerprint,verified,...}, ... ]
  send(peer,text)         -> {id, to}
  receive(peer?)          -> [ {id,from,name,text}, ... ]   (never --all)
  sync()                  -> {republished, replenished, ...}
  check_inbox()           -> convenience: receive from the configured peer(s)

Auto-receive
------------
1. Pull (works on stock codex today): the `receive` / `check_inbox` tools plus
   the AGENTS.snippet.md rule tell the agent to check for new mail each turn.
2. Forward-compatible push (no codex patch): when RETALK_WATCH_PEER is set the
   server runs `retalk receive --peer <fp> --follow` in the background and, for
   each new message, emits an MCP notification shaped like the alexfrmn
   `surface_notifications` design (method `notifications/message`, params carry
   toSession/msgId/source/text). On stock codex 0.144.x this is inert (ignored,
   not an error); it lights up if codex ships session-ingress for MCP
   notifications (openai/codex#15299). Deduped by msgId, opt-in, off by default.

This server does NOT patch codex and does NOT modify retalk.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio


SERVER_NAME = "agent-talk"
SERVER_VERSION = "0.1.0"

# retalk binary; override with RETALK_BIN if it is not on PATH.
RETALK_BIN = os.environ.get("RETALK_BIN", "retalk")


# --------------------------------------------------------------------------- #
# Identity / relay flags shared by every retalk invocation                    #
# --------------------------------------------------------------------------- #
def _identity_args() -> list[str]:
    """Build the `retalk` identity/relay flags from the server environment.

    Returns the argument list (never the passphrase — that goes via the child's
    environment, so it is not visible in the process list).
    """
    args: list[str] = []
    rdir = os.environ.get("RETALK_DIR")
    ruser = os.environ.get("RETALK_USER")
    if rdir:
        args += ["--dir", rdir]
    elif ruser:
        args += ["--user", ruser]
    else:
        raise RuntimeError(
            "no retalk identity configured: set RETALK_DIR (an identity "
            "directory) or RETALK_USER (a named identity) in the MCP server "
            "environment"
        )
    relay = os.environ.get("RETALK_RELAY")
    if relay:
        args += ["--relay", relay]
    api_key = os.environ.get("RETALK_API_KEY")
    if api_key:
        args += ["--api-key", api_key]
    return args


def _child_env() -> dict[str, str]:
    """Environment for the retalk child: pass the passphrase here (not on argv)."""
    env = dict(os.environ)
    # RETALK_PASSPHRASE / RETALK_HOME are already inherited via os.environ; we
    # simply make sure retalk sees a clean copy. Nothing to strip.
    return env


class RetalkError(RuntimeError):
    """A retalk CLI failure, surfaced to the MCP client as a clean tool error."""


def _classify_error(stderr: str, stdout: str) -> str:
    """Turn a noisy retalk failure into a short, actionable message."""
    blob = (stderr + "\n" + stdout).strip()
    low = blob.lower()
    if "pin mismatch" in low:
        return (
            "PIN MISMATCH: the relay served keys that do not match the peer's "
            "saved fingerprint — possible relay tampering. Nothing was sent or "
            "verified. Re-check the fingerprint out-of-band before retrying.\n"
            + blob
        )
    if any(
        s in low
        for s in (
            "connection refused",
            "failed to establish",
            "max retries",
            "timed out",
            "timeout",
            "name or service not known",
            "could not resolve",
            "connection error",
            "unreachable",
        )
    ):
        return (
            "RELAY UNREACHABLE: could not reach the retalk relay. Check the "
            "relay URL / that it is running, then retry.\n" + blob
        )
    return blob or "retalk failed with no output"


async def _run_retalk(
    subcommand: str,
    *extra: str,
    include_identity: bool = True,
) -> str:
    """Run `retalk <subcommand> [identity flags] [extra...]` and return stdout.

    Raises RetalkError (with a cleaned-up message) on non-zero exit.
    """
    if shutil.which(RETALK_BIN) is None and not os.path.isabs(RETALK_BIN):
        raise RetalkError(
            f"the `{RETALK_BIN}` CLI is not on PATH; install retalk or set "
            f"RETALK_BIN to its full path"
        )
    argv = [RETALK_BIN, subcommand]
    if include_identity:
        argv += _identity_args()
    argv += list(extra)

    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_child_env(),
    )
    out_b, err_b = await proc.communicate()
    out = out_b.decode("utf-8", "replace")
    err = err_b.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise RetalkError(_classify_error(err, out))
    return out


def _parse_ndjson(text: str) -> list[dict[str, Any]]:
    """Parse NDJSON (one JSON object per line); ignore blank lines."""
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # A stray non-JSON line (should not happen on stdout) — skip it.
            continue
    return rows


# --------------------------------------------------------------------------- #
# Tool implementations                                                        #
# --------------------------------------------------------------------------- #
async def tool_id() -> dict[str, Any]:
    out = await _run_retalk("id", "--json")
    # `retalk id --json` prints a single Contact-card JSON object.
    return json.loads(out.strip())


async def tool_add(fingerprint: str, name: str | None, verify: bool) -> dict[str, Any]:
    extra = [fingerprint]
    if name:
        extra += ["--peer", name]
    if verify:
        extra += ["--verify"]
    await _run_retalk("add", *extra)
    result: dict[str, Any] = {"added": fingerprint, "verified": bool(verify)}
    if name:
        result["name"] = name
    return result


async def tool_verify(peer: str) -> dict[str, Any]:
    await _run_retalk("verify", peer)
    return {"verified": peer}


async def tool_contacts() -> list[dict[str, Any]]:
    out = await _run_retalk("contacts", "--json")
    return _parse_ndjson(out)


async def tool_send(peer: str, text: str) -> dict[str, Any]:
    out = await _run_retalk("send", "--peer", peer, text)
    # `retalk send` prints a JSON receipt {"id","to"}.
    return json.loads(out.strip())


async def tool_receive(peer: str | None) -> list[dict[str, Any]]:
    target = peer or os.environ.get("RETALK_WATCH_PEER") or os.environ.get(
        "RETALK_RECEIVE_FROM"
    )
    if not target:
        raise RetalkError(
            "receive needs a peer: pass `peer`, or configure RETALK_WATCH_PEER / "
            "RETALK_RECEIVE_FROM in the server environment. (This server never "
            "runs `retalk receive --all`.)"
        )
    out = await _run_retalk("receive", "--peer", target)
    return _parse_ndjson(out)


async def tool_sync() -> dict[str, Any]:
    out = await _run_retalk("sync")
    # `retalk sync` prints a JSON summary on stdout (plus a human line on stderr).
    line = out.strip().splitlines()[0] if out.strip() else "{}"
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"raw": out.strip()}


# --------------------------------------------------------------------------- #
# Tool registry                                                               #
# --------------------------------------------------------------------------- #
TOOLS: list[types.Tool] = [
    types.Tool(
        name="id",
        description=(
            "Print this agent's own retalk identity (fingerprint = user id, "
            "identity key, display name). Share the fingerprint out-of-band so "
            "peers can add you. No relay contact."
        ),
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    types.Tool(
        name="add",
        description=(
            "Save a peer's 32-hex fingerprint as a contact so you can message "
            "them by name. Optionally set a local `name` label and `verify` "
            "(fetch+pin their keys from the relay now)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "fingerprint": {
                    "type": "string",
                    "description": "the peer's 32-hex user id (fingerprint)",
                },
                "name": {
                    "type": "string",
                    "description": "optional local label for this peer (e.g. 'bob')",
                },
                "verify": {
                    "type": "boolean",
                    "description": "immediately fetch and pin the peer's keys",
                    "default": False,
                },
            },
            "required": ["fingerprint"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="verify",
        description=(
            "Fetch and pin a saved peer's public keys against their fingerprint "
            "(explicit first-contact verification). Refuses with PIN MISMATCH if "
            "the relay's keys do not match. The peer must already be added."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "peer": {
                    "type": "string",
                    "description": "a saved peer name or 32-hex fingerprint",
                }
            },
            "required": ["peer"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="contacts",
        description=(
            "List saved peers as Contact objects (name, fingerprint, verified, "
            "keys). Your address book — who you can message."
        ),
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    types.Tool(
        name="send",
        description=(
            "Encrypt and send one message to a peer (a saved name or 32-hex "
            "fingerprint). Returns the send receipt {id, to}. First contact "
            "auto-verifies keys; a PIN MISMATCH means possible relay tampering."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "peer": {
                    "type": "string",
                    "description": "recipient: a saved peer name or 32-hex user id",
                },
                "text": {"type": "string", "description": "the message plaintext"},
            },
            "required": ["peer", "text"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="receive",
        description=(
            "Fetch and decrypt pending messages from ONE sender and return them "
            "as a list of {id, from, name, text}. If `peer` is omitted, uses the "
            "configured watch/receive-from peer. Never reads the whole mailbox "
            "(no --all). Call this at the start of a turn to check for new mail."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "peer": {
                    "type": "string",
                    "description": (
                        "the sender to read (a saved peer name or 32-hex id); "
                        "defaults to the configured peer"
                    ),
                }
            },
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="check_inbox",
        description=(
            "Convenience alias for `receive` with no arguments: check the "
            "configured peer for new messages. Returns a list of "
            "{id, from, name, text} (empty list if none)."
        ),
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    types.Tool(
        name="sync",
        description=(
            "Reconcile this identity with the relay: republish keys, replenish "
            "one-time keys, rotate the fallback, and resend unacknowledged mail. "
            "Use to retry stuck sends or recover after a relay reset."
        ),
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
]


# --------------------------------------------------------------------------- #
# Server wiring                                                               #
# --------------------------------------------------------------------------- #
app: Server = Server(SERVER_NAME)


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


def _ok(payload: Any) -> list[types.TextContent]:
    """Wrap a JSON-serialisable payload as MCP text content."""
    return [types.TextContent(type="text", text=json.dumps(payload, indent=2))]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    args = arguments or {}
    try:
        if name == "id":
            return _ok(await tool_id())
        if name == "add":
            return _ok(
                await tool_add(
                    fingerprint=args["fingerprint"],
                    name=args.get("name"),
                    verify=bool(args.get("verify", False)),
                )
            )
        if name == "verify":
            return _ok(await tool_verify(peer=args["peer"]))
        if name == "contacts":
            return _ok(await tool_contacts())
        if name == "send":
            return _ok(await tool_send(peer=args["peer"], text=args["text"]))
        if name == "receive":
            return _ok(await tool_receive(peer=args.get("peer")))
        if name == "check_inbox":
            return _ok(await tool_receive(peer=None))
        if name == "sync":
            return _ok(await tool_sync())
        raise RetalkError(f"unknown tool: {name}")
    except KeyError as e:
        # Missing required argument -> raise so MCP marks the tool call failed.
        raise RetalkError(f"missing required argument: {e.args[0]}") from e
    except RetalkError:
        raise
    except Exception as e:  # noqa: BLE001 — surface anything else cleanly
        raise RetalkError(f"{type(e).__name__}: {e}") from e


# --------------------------------------------------------------------------- #
# Forward-compatible push: watch the inbox, emit toSession notifications       #
# --------------------------------------------------------------------------- #
def _log(msg: str) -> None:
    print(f"[retalk-mcp] {msg}", file=sys.stderr, flush=True)


async def _emit_to_session(session: Any, msg: dict[str, Any]) -> None:
    """Emit an alexfrmn-style inbound notification for one received message.

    Shape (openai/codex#15299 / alexfrmn surface_notifications):
        method: "notifications/message"
        params: { toSession: true, msgId, source, text, ...standard log fields }

    We ride the STABLE `notifications/message` (logging) envelope — which has
    `extra="allow"` — and attach the toSession/msgId/source/text fields. On
    stock codex 0.144.x this is a plain, ignorable log notification (inert, does
    NOT error). If codex ships session-ingress for MCP notifications, the
    toSession=true marker routes it into the active session as a user turn.
    """
    msg_id = str(msg.get("id", ""))
    text = msg.get("text", "")
    sender = msg.get("name") or msg.get("from") or "peer"
    params = types.LoggingMessageNotificationParams(
        level="info",
        logger="agent-talk",
        data={
            "toSession": True,
            "msgId": msg_id,
            "source": sender,
            "text": text,
            "note": "new retalk message (agent-talk)",
        },
        # alexfrmn-style top-level markers (extra='allow' keeps them on the wire)
        toSession=True,
        msgId=msg_id,
        source=sender,
        text=text,
    )
    notification = types.ServerNotification(
        types.LoggingMessageNotification(
            method="notifications/message", params=params
        )
    )
    await session.send_notification(notification)


async def _watch_inbox(session: Any) -> None:
    """Tail `retalk receive --peer <fp> --follow` and push each new message.

    Opt-in: only runs when RETALK_WATCH_PEER is set. Deduped by msgId. Any
    failure is logged to stderr and the watcher backs off; it never crashes the
    server or the client session.
    """
    peer = os.environ.get("RETALK_WATCH_PEER")
    if not peer:
        return
    seen: set[str] = set()
    _log(f"push watcher enabled for peer={peer[:12]}… (toSession notifications)")
    while True:
        try:
            argv = [RETALK_BIN, "receive"] + _identity_args() + [
                "--peer",
                peer,
                "--follow",
            ]
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=_child_env(),
            )
            assert proc.stdout is not None
            async for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("kind") == "contact":
                    continue  # only surface chat messages
                mid = str(msg.get("id", ""))
                if mid and mid in seen:
                    continue
                if mid:
                    seen.add(mid)
                try:
                    await _emit_to_session(session, msg)
                    _log(f"emitted toSession notification for msg {mid[:12]}…")
                except Exception as e:  # noqa: BLE001
                    _log(f"notification emit failed (ignored): {e!r}")
            rc = await proc.wait()
            _log(f"follower exited rc={rc}; restarting in 5s")
        except Exception as e:  # noqa: BLE001
            _log(f"watcher error (backing off 5s): {e!r}")
        await asyncio.sleep(5)


async def main() -> None:
    """Own the ServerSession so the push watcher can hold a live handle to it.

    This mirrors `Server.run` (mcp low-level) but keeps a reference to the
    ServerSession, which `run()` does not expose. That lets the optional push
    watcher call `session.send_notification` for the whole connection lifetime.
    """
    import anyio
    from contextlib import AsyncExitStack
    from mcp.server.session import ServerSession

    # Validate identity config early so a misconfigured server fails loudly.
    try:
        _identity_args()
    except RuntimeError as e:
        _log(str(e))
        # Still start (list_tools works); tool calls report the same error.

    init_options = InitializationOptions(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        capabilities=app.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
        instructions=(
            "agent-talk over retalk: use `receive`/`check_inbox` at the start of "
            "a turn to pick up new end-to-end-encrypted messages, and `send` to "
            "reply. `id` shows your address; `add`/`verify` manage peers."
        ),
    )

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        async with AsyncExitStack() as stack:
            lifespan_context = await stack.enter_async_context(app.lifespan(app))
            session = await stack.enter_async_context(
                ServerSession(read_stream, write_stream, init_options)
            )
            async with anyio.create_task_group() as tg:
                if os.environ.get("RETALK_WATCH_PEER"):
                    tg.start_soon(_watch_inbox, session)
                async for message in session.incoming_messages:
                    tg.start_soon(
                        app._handle_message,
                        message,
                        session,
                        lifespan_context,
                        False,
                    )


if __name__ == "__main__":
    asyncio.run(main())
