#!/usr/bin/env python3
"""agent-talk inbox hook for Codex.

This is the Codex equivalent of Claude Code's inbox monitor. A background
follower (`retalk receive --peer <fingerprint> --follow --interval 60 --quiet`)
decrypts incoming messages and appends each one as a JSON line to the user's
spool file `<user>/inbox.ndjson`. This script reads the new lines from that
spool and hands them to Codex through its hook system, so a peer's message
surfaces in the session the user is already working in.

Codex calls it once per hook event, with the event as the first argument:

    inbox-hook.py session-start    -> new messages become extra context
    inbox-hook.py user-prompt      -> new messages ride along with what you type
    inbox-hook.py stop             -> new messages become a continuation prompt,
                                      which is what makes delivery automatic:
                                      when a turn ends, Codex starts another one
                                      to handle the message, with no typing.

Which spool(s) to read is set per session by the agent-talk init skill when the
delivery mode is "auto". It sets AGENT_TALK_CODEX_SPOOLS to a colon-separated
list of absolute inbox.ndjson paths before launching Codex. With that variable
unset the script exits silently, so installing the hooks does not change any
session that has not opted in.

Each spool has a cursor file (`<user>/.codex-hook-state.json`) holding the byte
offset already consumed and the ids already delivered. The cursor is advanced
BEFORE the message is handed to Codex, which matters most for the stop event: a
hook that reported the same message twice would block every turn forever.
"""

import json
import os
import sys

EVENTS = {
    "session-start": "SessionStart",
    "user-prompt": "UserPromptSubmit",
    "stop": "Stop",
}
STATE_NAME = ".codex-hook-state.json"
MAX_REMEMBERED_IDS = 500


def spools():
    raw = os.environ.get("AGENT_TALK_CODEX_SPOOLS", "")
    return [p for p in (part.strip() for part in raw.split(":")) if p]


def state_path(spool):
    return os.path.join(os.path.dirname(os.path.abspath(spool)), STATE_NAME)


def read_state(spool):
    try:
        with open(state_path(spool)) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return 0, []
    return int(data.get("offset", 0)), list(data.get("ids", []))


def write_state(spool, offset, ids):
    tmp = state_path(spool) + ".tmp"
    try:
        with open(tmp, "w") as fh:
            json.dump({"offset": offset, "ids": ids[-MAX_REMEMBERED_IDS:]}, fh)
        os.replace(tmp, state_path(spool))
    except OSError:
        pass  # a hook must never break the session over its own bookkeeping


def drain(spool):
    """Return the messages appended since the last run, advancing the cursor."""
    try:
        size = os.path.getsize(spool)
    except OSError:
        return []
    offset, seen = read_state(spool)
    if size < offset:
        offset = 0  # spool was truncated or rotated, start over
    if size == offset:
        return []
    try:
        with open(spool, "rb") as fh:
            fh.seek(offset)
            chunk = fh.read()
    except OSError:
        return []

    # Keep a partial trailing line for the next run: the follower may be
    # mid-write, and half a JSON record is not a message.
    consumed = len(chunk)
    if chunk and not chunk.endswith(b"\n"):
        cut = chunk.rfind(b"\n")
        if cut == -1:
            return []
        consumed = cut + 1
        chunk = chunk[:consumed]

    fresh, ids = [], list(seen)
    for line in chunk.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("kind") == "contact":
            continue  # shared contact cards are for the import skill, not chat
        text = record.get("text")
        if not text:
            continue
        mid = record.get("id")
        if mid and mid in ids:
            continue
        if mid:
            ids.append(mid)
        fresh.append({"name": record.get("name") or record.get("from") or "peer",
                      "text": text})
    write_state(spool, offset + consumed, ids)
    return fresh


def collect():
    messages = []
    for spool in spools():
        messages.extend(drain(spool))
    return messages


def render(messages):
    lines = []
    for msg in messages:
        lines.append(f"From {msg['name']}:\n{msg['text']}")
    return "\n\n".join(lines)


def main():
    event = EVENTS.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if event is None:
        print(f"usage: {os.path.basename(__file__)} "
              f"{{session-start|user-prompt|stop}}", file=sys.stderr)
        return 2
    if not spools():
        return 0  # auto delivery is off for this session
    try:
        sys.stdin.read()  # Codex sends the event payload; we do not need it
    except Exception:
        pass

    messages = collect()
    if not messages:
        return 0

    body = render(messages)
    count = len(messages)
    plural = "message" if count == 1 else "messages"
    if event == "Stop":
        # A blocked stop becomes a fresh user prompt, so write it as an
        # instruction rather than a status line.
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"{count} new agent-talk {plural} arrived while you were "
                f"working:\n\n{body}\n\n"
                "Show each message to the user verbatim as a chat transcript "
                "(quote the text, name the sender), then reply over agent-talk "
                "if it asks something, using the send skill. If no reply is "
                "needed, say so briefly and stop."
            ),
        }))
    else:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": (
                    f"{count} new agent-talk {plural} waiting:\n\n{body}\n\n"
                    "Surface these to the user verbatim as a chat transcript "
                    "before continuing with their request."
                ),
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
