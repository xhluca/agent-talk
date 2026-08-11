#!/usr/bin/env python3
"""Register the agent-talk inbox hooks with Codex.

Codex reads lifecycle hooks from `$CODEX_HOME/config.toml` (default
`~/.codex/config.toml`). This script appends the three agent-talk hook blocks
once and leaves an existing configuration otherwise untouched, so it is safe to
re-run. It also copies the optional `codex-with-daemon` launcher to
`~/.local/bin`; started through that launcher instead of plain `codex`, a
session attaches to Codex's app-server daemon and can be woken while idle (see
docs/codex-auto-receive.md). Installing the launcher changes nothing by itself:
plain `codex` keeps behaving exactly as before. The script prints what it did
and what the user still has to do by hand.

    python3 extensions/codex/install-hooks.py            # install
    python3 extensions/codex/install-hooks.py --check    # report only

Codex will not run hooks it has not been told to trust. The first Codex session
after installing shows a review prompt for these hooks; approving it once is
what arms auto-receive. Automation that already vets its hook sources can pass
`--dangerously-bypass-hook-trust` to `codex` instead.
"""

import argparse
import os
import sys

MARKER = "# >>> agent-talk inbox hooks >>>"
END = "# <<< agent-talk inbox hooks <<<"
LAUNCHER = "codex-with-daemon"

BLOCK = """{marker}
# Surfaces incoming agent-talk messages in this Codex session. Inert unless
# AGENT_TALK_CODEX_SPOOLS is set (the init skill sets it for auto delivery).
[[hooks.SessionStart]]
[[hooks.SessionStart.hooks]]
type = "command"
command = 'python3 "{script}" session-start'
async = false
statusMessage = "Checking agent-talk inbox"

[[hooks.UserPromptSubmit]]
[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = 'python3 "{script}" user-prompt'
async = false
statusMessage = "Checking agent-talk inbox"

[[hooks.Stop]]
[[hooks.Stop.hooks]]
type = "command"
command = 'python3 "{script}" stop'
async = false
statusMessage = "Checking agent-talk inbox"
{end}
"""


def codex_home():
    return os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")


def bin_dir():
    return os.path.join(os.path.expanduser("~"), ".local", "bin")


def read_file(path):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return None


def launcher_state(src, dest):
    """Return "current", "outdated", or "missing" for the installed copy."""
    have = read_file(dest)
    if have is None:
        return "missing"
    if have != read_file(src) or not os.access(dest, os.X_OK):
        return "outdated"
    return "current"


def on_path(directory):
    entries = os.environ.get("PATH", "").split(os.pathsep)
    return os.path.normpath(directory) in {os.path.normpath(e)
                                           for e in entries if e}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report whether the hooks and the launcher are "
                         "installed, change nothing")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, "inbox-hook.py")
    launcher_src = os.path.join(here, LAUNCHER)
    for needed in (script, launcher_src):
        if not os.path.exists(needed):
            print(f"{os.path.basename(needed)} not found next to this script "
                  f"({needed})", file=sys.stderr)
            return 1

    config = os.path.join(codex_home(), "config.toml")
    existing = read_file(config) or ""
    hooks_ok = MARKER in existing
    dest = os.path.join(bin_dir(), LAUNCHER)
    state = launcher_state(launcher_src, dest)

    if args.check:
        print(f"hooks {'installed' if hooks_ok else 'not installed'} "
              f"in {config}")
        print(f"launcher {'installed' if state == 'current' else state} "
              f"at {dest}")
        return 0 if hooks_ok and state == "current" else 1

    if hooks_ok:
        print(f"hooks already installed in {config}")
    else:
        os.makedirs(os.path.dirname(config), exist_ok=True)
        block = BLOCK.format(marker=MARKER, end=END, script=script)
        with open(config, "a") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write("\n" + block)
        print(f"installed agent-talk hooks in {config}")

    if state == "current":
        print(f"launcher already installed at {dest}")
    else:
        os.makedirs(bin_dir(), exist_ok=True)
        with open(dest, "w") as fh:
            fh.write(read_file(launcher_src))
        os.chmod(dest, 0o755)
        verb = "updated" if state == "outdated" else "installed"
        print(f"{verb} the {LAUNCHER} launcher at {dest}")
        print(f"  Optional: start Codex as `{LAUNCHER}` to make idle sessions "
              "wakeable. Plain `codex` is unchanged.")

    if not on_path(bin_dir()):
        print(f"note: {bin_dir()} is not on your PATH, so `{LAUNCHER}` will "
              "not run by name until you add it.")

    if not hooks_ok:
        print("Next: set AGENT_TALK_CODEX_SPOOLS to the spool path to watch "
              "before starting Codex, and approve the hook review prompt on "
              "the first run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
