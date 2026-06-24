#!/usr/bin/env bash
# Open the agent-talk chat pane to the RIGHT of the current (Claude) pane.
# Read-only Slack-style transcript; all terminal noise stays in the Claude pane.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.sh"         # AT_USER / AT_NAME drive the title + reader banner
TITLE="${AT_USER}·chat"

if [ -z "${TMUX:-}" ]; then
  echo "Not inside tmux — Option A needs a tmux session." >&2
  exit 1
fi

# If a chat pane is already open, just re-focus the Claude pane and exit.
if tmux list-panes -F '#{pane_title}' | grep -qx "$TITLE"; then
  echo "chat pane already open" >&2
  exit 0
fi

# Split current pane horizontally; new pane runs the reader with the same
# identity env, so its banner matches the pane title.
pane=$(tmux split-window -h -l '40%' -P -F '#{pane_id}' \
  "AT_USER='$AT_USER' AT_NAME='$AT_NAME' exec python3 '$DIR/reader.py'")
tmux select-pane -t "$pane" -T "$TITLE"
# hand focus back to the Claude pane on the left
tmux select-pane -L
echo "opened chat pane $pane" >&2
