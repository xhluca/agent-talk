#!/usr/bin/env python3
"""agent-talk spool writer: turn one follower's output into per-session spools.

A follower (`retalk receive --peer <peer> --follow --interval 60 --quiet`) emits
one JSON record per received message. Piping that through this writer, instead
of appending straight to `<user>/inbox.ndjson`, gives three things the old
single file could not:

  * A spool per session. Each record is copied to `<user>/sessions/<sid>.ndjson`
    for every session currently registered to this user, so two sessions sharing
    one identity each get their own copy and their own read position instead of
    racing for the same lines.
  * A bounded lifetime for decrypted text. A session spool is created when the
    session registers and swept when it is gone (`--gc`), so message bodies stop
    accumulating forever under the identity. retalk's own sealed history stays
    the durable, encrypted record.
  * An arrival timestamp. retalk records carry no time, so the writer stamps
    `ts` (UTC, ISO 8601) as each record lands.

Usage:
    retalk receive ... --follow --quiet | spool-writer.py --user <user-dir>
    spool-writer.py --user <user-dir> --gc      # sweep spools of dead sessions

Sessions are discovered from the map that `init` writes,
`~/.agent-talk/by-session/<session-id>` holding a user directory. A record is
written to every session whose map entry points at this user.

`--legacy` (on by default for one release) also appends to the old
`<user>/inbox.ndjson`, so a consumer still reading that path keeps working
during the transition. Pass `--no-legacy` to stop writing it.

`--wake-codex` (off by default) additionally tries, after each record lands,
to wake an idle Codex session through the app-server daemon's control socket,
so the session handles the mail instead of waiting for the next prompt. The
attempt is best-effort and pushes only a generic nudge, never the message
body; see bin/codex_wake.py and docs/codex-auto-receive.md. It is a flag
rather than automatic on socket presence because injecting turns is a real
capability: the user opts in once, in the command they can read.
"""

import argparse
import errno
import fcntl
import json
import os
import shutil
import sys
import time

try:
    import codex_wake                    # sibling module; used by --wake-codex
except ImportError:                      # tolerated until the flag asks for it
    codex_wake = None

DEFAULT_MAX_BYTES = 8 * 1024 * 1024      # rotate a spool past this size
DEFAULT_MAX_AGE_DAYS = 14                # sweep spools untouched for this long
SESSION_DIRNAME = "sessions"
REGISTRY = os.path.join("~", ".agent-talk", "by-session")


def registry_dir():
    return os.path.expanduser(REGISTRY)


def sessions_dir(user_dir):
    return os.path.join(user_dir, SESSION_DIRNAME)


def registered_sessions(user_dir):
    """Session ids whose map entry points at this user directory."""
    out = []
    target = os.path.realpath(user_dir)
    try:
        entries = os.listdir(registry_dir())
    except OSError:
        return out
    for sid in entries:
        path = os.path.join(registry_dir(), sid)
        try:
            with open(path) as fh:
                mapped = fh.read().strip()
        except OSError:
            continue
        if mapped and os.path.realpath(mapped) == target:
            out.append(sid)
    return out


def rotate_if_needed(path, max_bytes):
    if max_bytes <= 0:
        return
    try:
        if os.path.getsize(path) < max_bytes:
            return
    except OSError:
        return
    try:
        shutil.move(path, path + ".1")   # keep exactly one generation
    except OSError:
        pass


def append(path, line, max_bytes):
    """Append one line under an exclusive lock, rotating first if oversized."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rotate_if_needed(path, max_bytes)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, line.encode("utf-8"))
    except OSError:
        return False
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)
    return True


def stamp(raw):
    """Add an arrival timestamp, leaving anything unparseable untouched."""
    try:
        record = json.loads(raw)
    except ValueError:
        return raw if raw.endswith("\n") else raw + "\n"
    if isinstance(record, dict) and not record.get("ts"):
        record["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return json.dumps(record) + "\n"


def stream(args):
    user_dir = args.user
    os.makedirs(sessions_dir(user_dir), exist_ok=True)
    known, checked_at = [], 0.0
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        line = stamp(raw)
        now = time.monotonic()
        if now - checked_at > 5:          # re-read the registry at most every 5s
            known, checked_at = registered_sessions(user_dir), now
        spools = [os.path.join(sessions_dir(user_dir), sid + ".ndjson")
                  for sid in known]
        for spool in spools:
            append(spool, line, args.max_bytes)
        if args.legacy:
            append(os.path.join(user_dir, "inbox.ndjson"), line, args.max_bytes)
        if args.wake_codex and spools:
            # After the record is safely in the spool; a failed wake costs
            # nothing but the bounded attempt, and hooks still deliver.
            codex_wake.maybe_wake(user_dir, spools)
        sys.stdout.flush()
    return 0


def gc(args):
    """Remove session spools whose session is gone, or long untouched."""
    live = set(registered_sessions(args.user))
    directory = sessions_dir(args.user)
    cutoff = time.time() - args.max_age_days * 86400
    removed = []
    try:
        entries = os.listdir(directory)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return 0
        return 1
    for name in entries:
        if not name.endswith(".ndjson") and not name.endswith(".ndjson.1"):
            continue
        sid = name.split(".ndjson")[0]
        path = os.path.join(directory, name)
        try:
            untouched = os.path.getmtime(path) < cutoff
        except OSError:
            continue
        # Nothing removes registry entries, so a dead session usually still has
        # one: age is the main signal, and an unregistered session is gone for
        # certain. An active spool is written on every message, so its mtime
        # keeps it alive. Sweeping a quiet session's spool only drops already
        # delivered lines; retalk's sealed history remains the durable record.
        if sid in live and not untouched:
            continue
        try:
            os.remove(path)
            removed.append(name)
        except OSError:
            pass
    for name in removed:
        print(f"removed {name}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", required=True,
                    help="the agent-talk user directory (holds identity/, sessions/)")
    ap.add_argument("--gc", action="store_true",
                    help="sweep spools of sessions that are gone, then exit")
    ap.add_argument("--legacy", dest="legacy", action="store_true", default=True,
                    help="also append to the old <user>/inbox.ndjson (default)")
    ap.add_argument("--no-legacy", dest="legacy", action="store_false",
                    help="stop writing the old <user>/inbox.ndjson")
    ap.add_argument("--wake-codex", dest="wake_codex", action="store_true",
                    help="after each record, best-effort wake an idle Codex "
                         "session through the app-server daemon (opt-in; see "
                         "docs/codex-auto-receive.md)")
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES,
                    help="rotate a spool once it passes this size (0 disables)")
    ap.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS,
                    help="with --gc, also sweep spools untouched this long")
    args = ap.parse_args()
    args.user = os.path.abspath(os.path.expanduser(args.user))
    if args.wake_codex and codex_wake is None:
        print("--wake-codex needs codex_wake.py next to this script",
              file=sys.stderr)
        return 2
    return gc(args) if args.gc else stream(args)


if __name__ == "__main__":
    sys.exit(main())
