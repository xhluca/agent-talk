# Demos

One live **agent-to-agent conversation**, shown from both sides: **04-alice**
and **05-bob** were recorded simultaneously in two Claude Code sessions (two
docker sandboxes talking through a **temporary local relay**). All setup —
identity, keys, adding + verifying the peer, and arming the auto-receive wake
monitor — happens **before** the recording and is cleared away, so each clip
opens on a clean screen and both panes are active as a live two-way exchange
from the start: Alice's agent **opens** with a heads-up that the dataset is
ready, and Bob's agent replies with a question. The only human typing is
**one short prompt on 05-bob** (Bob's opening question); on **04-alice** the
human types **nothing at all**. Everything after that is the two agents talking
to each other over agent-talk on their own across several turns (9
messages, five from alice and four from bob): every message is **agent-authored**, and each incoming
message **wakes the receiving session by itself** (the receive skill's
persistent wake monitor fires; nobody types any conversation content). The
prompt types in quickly (~5s on screen) and the conversation plays at a
readable **1.5×**. The two casts share the **exact same total duration** and
are rendered to **identical GIF length** so they loop in lockstep side by side.
`.cast` files are asciinema recordings (replay with `asciinema play <file>`);
the GIFs are rendered with `agg` (zoomed in with a larger font size). Recorded at a 76x22 terminal so the text renders large in embeds.

The scenario mirrors the "Why agent-talk?" example in the top-level README:
Alice is a data engineer whose agent owns a freshly built dataset,
`customer-churn-v3`; Bob is a research scientist training a churn model on it,
and his agent has questions before it starts.

- **04-alice** — Alice's side. Her agent opens by telling Bob the dataset is
  ready, then answers his follow-ups truthfully from the dataset files: row
  count and target column, that v3's splits are **row-wise** (so a customer can
  leak across train/val/test), that the customer-grouped **v3.1** has the same
  schema and rows, and a friendly sign-off. No human typing on this side.
- **05-bob** — Bob's side of the same run. His one typed prompt is the opening
  question; his agent then drives the exchange — asking about row count and
  target, whether the splits leak, and whether v3.1 matches — before confirming
  it'll switch to v3.1. The mirror image of the transcript in 04-alice.
