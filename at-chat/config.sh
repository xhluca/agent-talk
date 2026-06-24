#!/usr/bin/env bash
# at-chat configuration — the SINGLE place for user-specific values.
#
# Edit the five values in the first block for your retalk identity. Every
# at-chat script sources this file, and the chat reader (reader.py) reads the
# same values — from the environment when launched by open-chat.sh, or by
# parsing this file directly for standalone runs. Nothing else in at-chat
# hard-codes an identity.

# ---- edit these for your identity --------------------------------------
AT_USER="alice"                                   # your retalk username
AT_ID="0123456789abcdef0123456789abcdef"          # your user id (fingerprint)
AT_RELAY="https://relay.example.com"              # relay base URL
AT_PEER="bob"                                     # default peer to follow / send to
AT_NAME=""                                        # chat banner name (blank = AT_USER)

# ---- derived; normally no need to edit below ---------------------------
: "${AT_NAME:=$AT_USER}"
AT_BASE="$HOME/.agent-talk/users/$AT_USER"        # spool + identity home
AT_IDDIR="$AT_BASE/identity"                      # retalk identity directory
AT_INBOX="$AT_BASE/inbox.ndjson"
AT_SENT="$AT_BASE/sent.ndjson"
AT_SEEN="$AT_BASE/seen.ndjson"

# Pattern that matches THIS identity's follow-reader supervisor (a bash loop
# whose argv contains the expanded inbox path) but not its retalk child (whose
# argv has no inbox path). Scoping by $AT_INBOX lets multiple at-chat users
# coexist on one host without start/stop/status touching each other's readers.
AT_SUP_PAT="retalk receive.*--follow.*${AT_INBOX}"

export AT_USER AT_ID AT_RELAY AT_PEER AT_NAME
export AT_BASE AT_IDDIR AT_INBOX AT_SENT AT_SEEN AT_SUP_PAT
