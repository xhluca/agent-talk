#!/usr/bin/env python3
"""agent-talk chat pane — a minimal, colorful Slack-style reader.

Renders the conversation as a colored transcript: a stable per-sender color,
a colored gutter bar down each message, grouped headers, timestamps, and
word-wrap. It follows BOTH sides of the conversation, one spool each:

  * incoming -> the user's inbox spool  (written by the retalk follow-reader)
  * outgoing -> the user's sent spool   (written on each send)

Your own messages (everything in the sent spool) are tagged "(you)", given a
fixed color, and right-aligned; everyone else is left-aligned. "Yours" is
decided by which spool a line came from, so no identity/fingerprint is needed.

Timestamps: outgoing messages carry a real ``ts``; incoming lines have none,
so the reader stamps each one when first seen and persists that to a sidecar
so times stay stable across restarts. Read-only; live.

Configuration: all identity values come from config.sh (the single source) —
read from the environment when launched by open-chat.sh, or parsed straight
from config.sh beside this file for standalone runs. Individual env vars still
override: AT_USER, AT_NAME, AT_INBOX, AT_SENT, AT_SEEN. Nothing here hard-codes
an identity.

Known limitation: column math counts code points, not display cells, so a wide
glyph (emoji / CJK) shifts wrapping and the right-aligned gutter by a column.
Plain text aligns exactly.
"""
import hashlib
import json
import os
import re
import shutil
import signal
import sys
import textwrap
import time
from datetime import datetime

HOME = os.path.expanduser("~")


def _config(key, default=""):
    """Resolve a user-specific value: environment first (exported by the
    at-chat scripts), else parsed from config.sh beside this file. Keeps
    reader.py free of any hard-coded identity."""
    env = os.environ.get(key)
    if env:
        return env
    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.sh")
    try:
        with open(cfg, encoding="utf-8") as f:
            for line in f:
                m = re.match(r'\s*' + re.escape(key) + r'="?([^"#\n]*)"?', line)
                if m and m.group(1).strip():
                    return m.group(1).strip()
    except OSError:
        pass
    return default


USER = _config("AT_USER")
NAME = _config("AT_NAME", USER)
BASE = f"{HOME}/.agent-talk/users/{USER}"
INBOX = os.environ.get("AT_INBOX") or f"{BASE}/inbox.ndjson"
SENT = os.environ.get("AT_SENT") or f"{BASE}/sent.ndjson"
SEEN = os.environ.get("AT_SEEN") or f"{BASE}/seen.ndjson"

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
GUTTER = "▎"
# distinct, readable 256-color codes for stable per-sender coloring
PALETTE = [208, 46, 201, 214, 51, 213, 118, 111, 179, 165, 154, 39]
YOU_COLOR = 45  # your messages always wear this color, whoever you talk to

_seen = {}  # message id -> ISO timestamp of first sighting


def col(code):
    return f"\033[38;5;{code}m"


def color_for(fp):
    h = int(hashlib.sha1(fp.encode()).hexdigest(), 16)
    return PALETTE[h % len(PALETTE)]


def pane_width():
    cols = shutil.get_terminal_size((80, 24)).columns
    return max(20, cols)  # full pane width


def right_edge():
    return pane_width() - 1  # keep the last column blank (avoid auto-wrap)


def wrap_width():
    return max(16, right_edge() - 2)  # full width, less the gutter + a space


def parse(line):
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def load_seen():
    if os.path.exists(SEEN):
        with open(SEEN, "r", encoding="utf-8") as f:
            for rec in (parse(l) for l in f):
                if rec and rec.get("id"):
                    _seen[rec["id"]] = rec.get("ts")


def time_of(msg):
    """Resolve a message's timestamp (own ts, else a recorded first-seen)."""
    return msg.get("ts") or _seen.get(msg.get("id"))


def stamp(msg):
    """Record+persist a first-seen time for a freshly arrived message that
    carries no ts of its own (incoming lines). No-op once already known."""
    mid = msg.get("id")
    if msg.get("ts") or not mid or mid in _seen:
        return
    iso = datetime.now().isoformat(timespec="seconds")
    _seen[mid] = iso
    with open(SEEN, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": mid, "ts": iso}) + "\n")


def time_str(iso):
    """Plain HH:MM (or with date) for an ISO timestamp; '··:··' if unknown."""
    if not iso:
        return "··:··"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return "··:··"
    fmt = "%H:%M" if dt.date() == datetime.now().date() else "%b %d %H:%M"
    return dt.strftime(fmt)


def fmt_time(iso):
    return f"{DIM}{time_str(iso)}{RESET}"


def render(msg, prev_from):
    mine = msg.get("_mine", False)  # from the sent spool -> yours, right-aligned
    frm = msg.get("from", "")
    name = msg.get("name") or (frm[:8] if frm else "?")
    label = f"{name} (you)" if mine else name
    c = col(YOU_COLOR if mine else color_for(frm or name))
    bar = f"{c}{GUTTER}{RESET}"
    iso = time_of(msg)
    t = fmt_time(iso)
    edge = right_edge()

    def emit(plain, colored):
        # Right-pad yours to the right edge (measuring the plain text, which
        # has no ANSI); leave received lines flush left.
        return " " * max(0, edge - len(plain)) + colored if mine else colored

    out = [""]  # blank line separates every message, grouped or not

    # Header: a new sender gets a name + dot; a follow-on shows just the time.
    if frm != prev_from and mine:
        out.append(emit(f"{time_str(iso)}  {label} ●",
                        f"{c}{t}  {c}{BOLD}{label}{RESET} {c}●{RESET}"))
    elif frm != prev_from:
        out.append(f"{c}●{RESET} {c}{BOLD}{label}{RESET}  {c}{t}")
    elif mine:
        out.append(emit(f"{time_str(iso)} {GUTTER}", f"{c}{t} {bar}"))
    else:
        out.append(f"{bar} {t}")

    # Body: one wrap/paragraph pass for both sides; gutter trails yours.
    for para in msg.get("text", "").split("\n"):
        if not para.strip():
            out.append(emit(GUTTER, bar) if mine else bar)
            continue
        for ln in textwrap.wrap(para, wrap_width()):
            out.append(emit(f"{ln} {GUTTER}", f"{ln} {bar}") if mine else f"{bar} {ln}")
    return "\n".join(out)


def rule(text):
    n = max(0, pane_width() - len(text) - 3)
    return f"{DIM}─ {text} {'─' * n}{RESET}"


def main():
    load_seen()

    # One handle per spool, opened lazily and kept at EOF between reads so the
    # same call serves the startup backlog and every later tail. Only complete
    # (newline-terminated) lines are consumed; a half-written final line waits.
    handles = {}

    def drain(path, mine):
        if path not in handles and os.path.exists(path):
            handles[path] = open(path, "r", encoding="utf-8")
        f = handles.get(path)
        out = []
        while f:
            pos = f.tell()
            line = f.readline()
            if not line or not line.endswith("\n"):
                f.seek(pos)
                break
            m = parse(line)
            if m:
                m["_mine"] = mine  # tag by source spool; drives alignment/color
                out.append(m)
        return out

    def poll():
        return drain(INBOX, False) + drain(SENT, True)

    # Full message history, in order: backlog first, then live arrivals.
    # Kept in memory so the whole transcript can be re-rendered on resize.
    msgs = poll()
    n_backlog = len(msgs)

    # SIGWINCH (pane resize) -> repaint the whole transcript at the new width,
    # so right-aligned (your) messages re-align instead of overflowing/wrapping.
    state = {"resized": True, "width": pane_width()}

    def on_winch(*_):
        state["resized"] = True

    try:
        signal.signal(signal.SIGWINCH, on_winch)
    except (ValueError, AttributeError, OSError):
        pass  # no controlling terminal / unsupported platform

    def repaint(messages, prev=None):
        for m in messages:
            print(render(m, prev))
            prev = m.get("from")
        return prev

    def redraw():
        sys.stdout.write("\033[2J\033[H")  # clear screen
        sys.stdout.write(f"{col(YOU_COLOR)}{BOLD}{NAME}{RESET} {DIM}· agent-talk{RESET}\n\n")
        prev = None
        if n_backlog:
            print(rule("earlier"))
            prev = repaint(msgs[:n_backlog])
        print()
        print(rule("live"))
        repaint(msgs[n_backlog:], prev)
        sys.stdout.flush()
        state["width"] = pane_width()
        state["resized"] = False

    while True:
        new = poll()
        for m in new:
            stamp(m)  # record first-seen times before anything renders

        if state["resized"] or pane_width() != state["width"]:
            msgs.extend(new)
            redraw()
        elif new:
            prev = msgs[-1].get("from") if msgs else None
            repaint(new, prev)
            sys.stdout.flush()
            msgs.extend(new)
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
