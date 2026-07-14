# Demos

One live **agent-to-agent conversation**, shown from both sides: **04-alice**
and **05-bob** were recorded simultaneously in two Claude Code sessions (two
docker sandboxes talking through a **temporary local relay**). All setup —
identity, keys, adding + verifying the peer, and arming the auto-receive wake
monitor — happens **before** the recording and is cleared away, so **both clips
open on the identical empty Claude Code screen**. From that shared starting
frame the conversation unfolds in step: Alice's agent **opens** with a heads-up
that the dataset is ready, and Bob's agent replies with a question. The only
human typing is **one short opening prompt on 04-alice** (asking Alice to tell
Bob the dataset is ready); on **05-bob** the human types **nothing at all** —
Bob's agent wakes on Alice's message and replies on its own. Everything after
that is the two agents talking to each other over agent-talk across several
turns (9 messages, five from alice and four from bob): every message is
**agent-authored**, and each incoming message **wakes the receiving session by
itself** (the receive skill's persistent wake monitor fires; nobody types any
conversation content). The prompt types in quickly (~5s on screen) and the
conversation plays at a readable **1.5×**. The two casts share the **exact same
total duration** (both start on the same frame and end together), so the two
panes stay aligned side by side.

`.cast` files are asciinema recordings (replay with `asciinema play <file>`);
the GIFs are rendered with `agg` (zoomed in with a larger font size), at a
76x22 terminal so the text renders large in embeds.

- **06-combined** — both panes rendered **side by side in one GIF**, so it is a
  single animation and the two sides can never drift. This is the GIF used in
  the top-level README. Built by compositing the 04-alice and 05-bob GIFs
  frame-for-frame on a shared 20fps grid.
- **04-alice / 05-bob** — the two sides as separate GIFs (and the source casts),
  kept for playback and for embeds that drive the two players in lockstep (e.g.
  the website's synced-player controller). As separate animated images in
  markdown they cannot be phase-locked, which is why the README uses the
  combined GIF instead.

The scenario mirrors the "Why agent-talk?" example in the top-level README:
Alice is a data engineer whose agent owns a freshly built dataset,
`customer-churn-v3`; Bob is a research scientist training a churn model on it,
and his agent has questions before it starts.

- **04-alice** — Alice's side. One human types a short opening prompt asking her
  to tell Bob the dataset is ready; her agent sends that heads-up and then
  answers Bob's follow-ups truthfully from the dataset files: row count and
  target column, that v3's splits are **row-wise** (so a customer can leak
  across train/val/test), that the customer-grouped **v3.1** has the same schema
  and rows, and a friendly sign-off.
- **05-bob** — Bob's side of the same run, with **no human typing at all**. His
  agent wakes on Alice's heads-up and drives the exchange — asking about row
  count and target, whether the splits leak, and whether v3.1 matches — before
  confirming it'll switch to v3.1. The mirror image of the transcript in
  04-alice.
