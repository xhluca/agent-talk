#!/usr/bin/env python3
"""Register the agent-talk inbox hooks with Codex.

Codex reads lifecycle hooks from `$CODEX_HOME/config.toml` (default
`~/.codex/config.toml`). This script appends the three agent-talk hook blocks
once and leaves an existing configuration otherwise untouched, so it is safe to
re-run. It prints what it did and what the user still has to do by hand.

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report whether the hooks are installed, change nothing")
    args = ap.parse_args()

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "inbox-hook.py")
    if not os.path.exists(script):
        print(f"inbox-hook.py not found next to this script ({script})",
              file=sys.stderr)
        return 1

    config = os.path.join(codex_home(), "config.toml")
    existing = ""
    if os.path.exists(config):
        with open(config) as fh:
            existing = fh.read()

    if MARKER in existing:
        print(f"already installed in {config}")
        return 0
    if args.check:
        print(f"not installed in {config}")
        return 1

    os.makedirs(os.path.dirname(config), exist_ok=True)
    block = BLOCK.format(marker=MARKER, end=END, script=script)
    with open(config, "a") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write("\n" + block)
    print(f"installed agent-talk hooks in {config}")
    print("Next: set AGENT_TALK_CODEX_SPOOLS to your inbox.ndjson path before "
          "starting Codex, and approve the hook review prompt on the first run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
