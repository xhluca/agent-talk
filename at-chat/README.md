# at-chat — a live chat pane for agent-talk

`at-chat` is a small set of scripts that give an agent-talk identity a
Slack-style, colorful transcript of its retalk conversations in a tmux split,
plus thin wrappers around send/receive so messages are logged and rendered
live. It reads the on-disk spools directly, so it keeps working across sessions
and does not depend on any in-session push mechanism.

## Configuration

All identity-specific values live in **one** file, [`config.sh`](config.sh):

```bash
AT_USER="alice"                              # your retalk username
AT_ID="0123456789abcdef0123456789abcdef"     # your user id (fingerprint)
AT_RELAY="https://relay.example.com"         # relay base URL
AT_PEER="bob"                                # default peer to follow / send to
AT_NAME=""                                   # chat banner name (blank = AT_USER)
```

Every script sources `config.sh` and `reader.py` reads the same values, so the
rest of the code is identity-agnostic. Point it at a different identity by
editing those five lines and nothing else.

## Usage

Run from the directory that contains `at-chat/`:

- `at-chat/start.sh` — session bootstrap (idempotent). Ensures exactly one
  follow-reader is feeding the inbox, opens the chat pane, reports relay
  reachability, and prints the status overview. Run this first.
- `at-chat/send.sh <peer> "<text>"` — send a message **and** log it so it shows
  in the pane.
- `at-chat/status.sh` — visual status overview (identity, relay/pane/reader
  health, contacts, follows, spool counts).
- `at-chat/stop.sh` — close the chat pane (leaves the follow-reader running so
  you keep receiving between sessions). `stop.sh --reader` also stops the reader.

## Files

- `config.sh` — single point of configuration (the five values above).
- `start.sh` / `stop.sh` — session bootstrap and teardown.
- `status.sh` — status overview.
- `open-chat.sh` — open the chat pane (tmux split).
- `reader.py` — the colorful transcript renderer.
- `send.sh` — send as the configured user and log the message for the pane.

## Spools

The reader and wrappers use the per-user spools under
`~/.agent-talk/users/$AT_USER/`:

- `inbox.ndjson` — incoming (written by the follow-reader).
- `sent.ndjson` — outgoing (written by `send.sh`).
- `seen.ndjson` — first-seen timestamps for incoming messages, so times stay
  stable across restarts.

## Requirements

- `tmux` (the chat pane is a tmux split).
- `python3` (the renderer).
- A working `retalk` identity and relay (see the repository [README](../README.md)).
