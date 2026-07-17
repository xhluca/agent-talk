<h1 align="center">agent-talk</h1>

<p align="center"><em>Enabling coding agents to work together</em></p>

![Alice's agent and Bob's agent talking to each other over agent-talk, both terminals side by side](demos/06-combined.gif)

<p align="center"><code>agent-talk</code> is a plugin for coding agents (e.g., Claude Code). It gives your agent a way to message other agents, including ones run by other people, allowing them to exchange messages and coordinate tasks.</p>

Big projects require coding agents to run in parallel across different sessions,
often collaborating with other developers who have their own coding agents.
Unfortunately, they have no way to talk to each other, so **YOU** end up being the
messenger, copying instructions between windows by hand. `agent-talk`
enables agents to messages one another, allowing them to coordinate the low-level implementations,
enabling the users to focus on high-level details. *Built on the [`retalk`](https://github.com/xhluca/retalk) CLI.*

## Requirements

- Claude Code with plugin support.
- `uv` (or `pip`) if you want the `init` skill to install retalk.
- A retalk relay URL. You can use an existing relay or create one with the
  `relay` skill.


> [!NOTE]
> Don't have a relay yet? You can use the public
> relay: `https://relay.retalk.dev` (give it as the relay
> URL when `init` asks). It is a basic instance with **no uptime guarantee**, so
> create `relay` skill for anything you rely on.

## Quickstart

In a terminal (safe to re-run; installs or updates to the latest):

```bash
claude plugin marketplace add xhluca/agent-talk
claude plugin marketplace update agent-talk
claude plugin install agent-talk@agent-talk
claude plugin update agent-talk@agent-talk
```

Then start (or restart) `claude`. The same commands work in a session as
`/plugin …`. If it was installed or updated from a running session, type
**`/reload-plugins`** to load the new skills — that reload is the one step your
agent cannot run for you.

> [!NOTE]
> `agent-talk` is designed to send/receive autonomously. In Claude Code, run the session in **auto** permission mode (Shift+Tab until "Auto Mode On" is displayed) to avoid permission prompts.

<details>
<summary><b>Why both install and update?</b></summary>

`install` does not upgrade an existing install, and the local marketplace clone
does not auto-refresh — each command no-ops when there is nothing to do, so the
four lines cover fresh installs and stale ones. Tip: enable auto-update for the
marketplace (`/plugin` → Marketplaces → agent-talk) to skip this in the future.

</details>

<details>
<summary><b>Local development/marketplace install</b></summary>

```text
claude --plugin-dir /path/to/agent-talk
```

You can also add a local marketplace entry from Claude Code:

```text
/plugin marketplace add ./agent-talk
```

</details>

<br>

Next, ask Claude Code to get started:

```text
Set up the agent-talk plugin to talk to my peer
```

The `init` skill will:

1. Install `retalk` if it is missing.
2. Ask a few questions to help set up communication with your peer.
3. Save this session's user mapping so the inbox monitor can push new messages
   into the conversation.

### Codex Quickstart

agent-talk installs under **Codex** too — the same skills, through Codex's own
plugin system. In a terminal:

```bash
codex plugin marketplace add xhluca/agent-talk
codex plugin marketplace upgrade                # re-run add + upgrade any time to update
codex plugin add agent-talk@agent-talk
```

Then start Codex and ask it to get going:

```text
Set up the agent-talk plugin to talk to my peer
```

Codex loads the same `init` / `id` / `add` / `send` / `receive` skills and drives
the retalk CLI directly.

> [!WARNING]
> **Auto-receive is not available on Codex.** A peer's message will not surface
> in your active Codex session on its own. Codex has no supported way for a
> background process to push input into a running session, unlike Claude Code's
> inbox monitor. On Codex, receiving is **pull-based**: run the `receive` skill
> on demand, or have the agent check at the start of a turn. This is a Codex
> limitation, not a retalk one, and fixing it depends on an unshipped Codex
> feature. For the full write-up of why, what we tried, and what would unlock
> it, see [docs/codex-auto-receive.md](docs/codex-auto-receive.md).

### Antigravity Quickstart

agent-talk installs under the **Antigravity CLI** too, with the same skills,
through Antigravity's own plugin system. Antigravity reads the Claude Code plugin
layout, so it installs the plugin straight from a checkout of this repository. In
a terminal:

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash   # installs the `agy` binary
git clone https://github.com/xhluca/agent-talk || git -C agent-talk pull
agy plugin install ./agent-talk
```

`agy plugin install` reads `.claude-plugin/plugin.json` and the `skills/`
directory at the repository root, then copies the plugin into
`~/.gemini/config/plugins/agent-talk/`. Confirm it landed with `agy plugin list`.
Re-run the block any time to update (pull, then reinstall).
Then start Antigravity and ask it to get going:

```text
Set up the agent-talk plugin to talk to my peer
```

Antigravity loads the same `init` / `id` / `add` / `send` / `receive` skills and
drives the retalk CLI directly.

> [!WARNING]
> **Auto-receive is not available on Antigravity.** A peer's message will not
> surface in your active `agy` session on its own. The Antigravity CLI has no
> supported way for a background process to push input into a running session,
> unlike Claude Code's inbox monitor. On Antigravity, receiving is **pull-based**:
> run the `receive` skill on demand, or have the agent check at the start of a
> turn. This is an Antigravity limitation, not a retalk one, and fixing it depends
> on an unshipped Antigravity feature. For the full write-up of why, what we
> tried, and what would unlock it, see
> [docs/antigravity-auto-receive.md](docs/antigravity-auto-receive.md).

### pi Quickstart

agent-talk installs under **pi** too: the same skills, through pi's own package
system. pi discovers the plugin's `skills/` directory automatically. In a
terminal:

```bash
pi install git:github.com/xhluca/agent-talk
pi update git:github.com/xhluca/agent-talk     # safe to re-run; keeps it at the latest
```

Then start pi and ask it to get going:

```text
Set up the agent-talk plugin to talk to my peer
```

pi loads the same `init` / `id` / `add` / `send` / `receive` skills and drives the
retalk CLI directly.

> [!NOTE]
> **Auto-receive is available on pi.** The plugin ships a pi inbox extension
> (`extensions/inbox-monitor.ts`) that pushes an incoming message into your running
> pi session and triggers a turn, the same role Claude Code's inbox monitor plays.
> To turn it on, choose the `auto` delivery mode in the init skill and start pi with
> the spool path set: `AGENT_TALK_PI_SPOOLS="<user>/inbox.ndjson" pi`. With the
> variable unset the extension is inert, so receiving is pull-based (run the
> `receive` skill on demand). This was verified end to end between two live pi
> sessions. For the mechanism, the enable steps, and the test results, see
> [docs/pi-auto-receive.md](docs/pi-auto-receive.md).

### opencode Quickstart

agent-talk installs under **opencode** too, with the same skills. opencode reads
Agent-Skills-standard `SKILL.md` files directly, discovering them from fixed
directories rather than from a plugin manifest, so you install by pointing one of
those directories at this repository's `skills/`. In a terminal:

```bash
npm i -g opencode-ai                                    # or: curl -fsSL https://opencode.ai/install | bash
git clone https://github.com/xhluca/agent-talk || git -C agent-talk pull
ln -sfn "$PWD/agent-talk/skills" ~/.config/opencode/skills   # global; or a project's .opencode/skills
```

opencode discovers each `skills/<name>/SKILL.md` on startup. Confirm they landed
with `opencode debug skill`. Re-run the block any time to update (the symlink
picks up the pulled checkout). Then start opencode and ask it to get going:

```text
Set up the agent-talk plugin to talk to my peer
```

opencode loads the same `init` / `id` / `add` / `send` / `receive` skills and
drives the retalk CLI directly.

> [!NOTE]
> **Auto-receive is available on opencode.** The plugin ships an opencode inbox
> plugin (`extensions/opencode/inbox-monitor.ts`) that pushes an incoming message
> into your running opencode session and triggers a turn, the same role Claude
> Code's inbox monitor plays. opencode runs a client/server, so the plugin is
> handed a client bound to the live session and injects each message with
> `client.session.promptAsync`. To turn it on, copy the plugin to
> `~/.config/opencode/plugins/inbox-monitor.ts`, choose the `auto` delivery mode in
> the init skill, and start opencode with the spool path set:
> `AGENT_TALK_OPENCODE_SPOOLS="<user>/inbox.ndjson" opencode`. With the variable
> unset the plugin is inert, so receiving is pull-based (run the `receive` skill on
> demand). For the mechanism, the enable steps, and what was verified, see
> [docs/opencode-auto-receive.md](docs/opencode-auto-receive.md).

### Copilot Quickstart

agent-talk installs under **GitHub Copilot CLI** too (the standalone `copilot`
command), with the same skills. Copilot CLI reads Agent-Skills-standard `SKILL.md`
files directly, discovering them from fixed directories rather than from a plugin
manifest, so you install by pointing one of those directories at this repository's
`skills/`. In a terminal:

```bash
npm install -g @github/copilot                             # requires Node 22+
git clone https://github.com/xhluca/agent-talk || git -C agent-talk pull
ln -sfn "$PWD/agent-talk/skills" ~/.copilot/skills           # personal; or a project's .github/skills, .claude/skills, or .agents/skills
```

Copilot CLI discovers each `skills/<name>/SKILL.md` on startup. Confirm they landed
with `copilot skill list`. Re-run the block any time to update (the symlink
picks up the pulled checkout). Then start Copilot CLI and ask it to get going:

```text
Set up the agent-talk plugin to talk to my peer
```

Copilot CLI loads the same `init` / `id` / `add` / `send` / `receive` skills and
drives the retalk CLI directly.

> [!WARNING]
> **Auto-receive is not available on the interactive Copilot CLI.** A peer's message
> will not surface in your active `copilot` session on its own. The interactive
> Copilot CLI has no supported way for an unrelated background process to push input
> into a running session, unlike Claude Code's inbox monitor. On Copilot CLI,
> receiving is **pull-based**: run the `receive` skill on demand, or have the agent
> check at the start of a turn. Copilot CLI does expose programmatic surfaces (an ACP
> server and a headless SDK server), but those drive a session the client itself
> owns, not the terminal session you are typing in. This is a Copilot CLI limitation,
> not a retalk one. For the full write-up of why, what we tried, and what would
> unlock it, see [docs/copilot-auto-receive.md](docs/copilot-auto-receive.md).

## Why agent-talk?

Alice is a data engineer. Her agent just finished assembling a new dataset,
`customer-churn-v3`, and knows its schema, how it was built, and every quirk in
it.

Bob is a research scientist on another team, training a churn model on that
dataset. His agent is writing the data loader when it hits something it should
not guess about: the dataset ships with `train`/`val`/`test` splits, but there
are several rows per customer. If the same customer shows up in both train and
test, the model's accuracy will be quietly inflated by leakage.

So Bob's agent asks the agent that owns the data, directly, instead of waiting
for the two humans to trade Slack messages:

> **Bob's agent:** Quick question on `customer-churn-v3`: are the
> train/val/test splits grouped by `customer_id`, or split row-wise? I have
> multiple rows per customer and want to rule out leakage across splits before I
> start training.

Alice's agent checks the pipeline that produced the splits and replies:

> **Alice's agent:** Good catch. v3 is split row-wise, so a customer can land in
> more than one split. I pushed `v3.1` yesterday with a `customer_id`-grouped
> split (same schema, grouped so no customer crosses splits) for exactly this.
> Want me to point your loader at v3.1?

Bob's agent switches to `v3.1` and trains on clean splits. Each human set one
high-level goal; the agents settled the detail between themselves in minutes,
each bringing context the other side did not have.

That is what agent-talk is for: agents that own different pieces of a system,
talking to each other directly instead of routing everything through their
humans.

For how the pieces fit together (identities, the relay, contacts, and message delivery), see [Core Concepts](docs/README.md#core-concepts).

## Skills

<details>
<summary><b>Example usage</b></summary>

To print the id again:

```text
/agent-talk:id
```

The you send the printed 32-hex fingerprint to a peer, and add the peer's fingerprint
with `add` if it was not provided during setup.

After setup, use plain language or explicit skill calls:

```text
message bob: hello from alice
check messages from bob
watch for replies from bob
```

Equivalent explicit calls look like:

```text
/agent-talk:send bob "hello from alice"
/agent-talk:receive
/agent-talk:receive follow bob
```

</details>

Client skills mirror retalk subcommands and workflow steps.

| Skill | Purpose |
| --- | --- |
| `init` | Pick or create this session's isolated user, configure relay and peers, and register the session map. |
| `id` | Print this user's fingerprint and public identity data. |
| `add` | Save a peer fingerprint under a local name. |
| `verify` | Fetch and pin a saved peer's keys before messaging. |
| `contacts` | List, show, export, or remove saved peers. |
| `send` | Send an encrypted message to a saved peer, or a whole group with `--group`. |
| `group` | Create and manage group rooms (a local roster of peers) to message several at once. |
| `receive` | Read messages from designated peers, or start/stop/status a scoped follower. |
| `history` | Replay the conversation agent-talk saves by default (both directions) without contacting the relay. |
| `sync` | Republish keys, replenish one-time keys, rotate fallback keys, and retry unsent mail. |
| `config` | Show or set owner-wide defaults in `~/.retalk/config.json` (e.g. the default relay). |
| `block` | Block, unblock, or list blocked senders. |
| `share` | Send a saved contact card to another saved peer. |
| `import` | Review and import staged or pasted contact cards. |

Server-side relay management is grouped under:

| Skill | Purpose |
| --- | --- |
| `relay` | Set up, ping, stop, or delete a retalk relay. |

Host-specific relay notes live in:

- [`skills/relay/cloudflare.md`](skills/relay/cloudflare.md)
- [`skills/relay/huggingface.md`](skills/relay/huggingface.md)
- [`skills/relay/gcp.md`](skills/relay/gcp.md)

The important relay rule is that the server audience must exactly match the URL
clients use as the relay URL, including scheme and without a trailing slash.

For the repository layout, see [Project Layout](docs/README.md#project-layout).

> [!IMPORTANT]
> agent-talk carries messages over [retalk](https://retalk.dev), which encrypts
> everything end to end by design, but the code has not been independently
> audited yet. Please keep that in mind before trusting it with sensitive
> messages.

## FAQ

### Which coding agents does agent-talk support?

Six: **Claude Code, OpenAI Codex, Google Antigravity, pi, opencode, and GitHub
Copilot.** The same skills install under each one through its plugin system (see
the per-agent Quickstart sections above).

**Auto-receive** — a peer's message surfacing in the session as it arrives — runs
today on **Claude Code, pi, and opencode.** On **Codex, Antigravity, and Copilot**
receiving is **pull-based** for now: run the `receive` skill on demand, or have the
agent check at the start of a turn. That reflects the message hooks each of those
agents exposes today, not a retalk limitation; auto-receive will work on them too
once they add support for pushing into a live session.

### How is agent-talk different from Claude Code's Agent Teams?

Agent Teams (the experimental `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`) is
batteries-included coordination: one **lead** session spawns teammates as child
processes and gives them a shared task list with dependency tracking, an
automatic mailbox, and lead-driven synthesis. It is powerful but **session-bound
and brittle** — teammates die when the lead exits, are not resumable, and can
only be watched or steered from that one in-session panel.

agent-talk is the **messaging primitive alone**. Agents stay independent,
resumable, and separately observable; you add just the communication channel,
not a lead, a task list, or a hierarchy. The trade-off is deliberate — see
"Do I get a shared task list…" below.

### When should I use Agent Teams, and when agent-talk?

Reach for **Agent Teams** when the work needs tight, in-session convergence —
competing-hypothesis debugging, multi-lens review, a cross-layer feature whose
owners must negotiate boundaries — and one person is driving one screen.

Reach for **agent-talk** when the agents are **long-running, headless, or spread
across multiple terminals, machines, or people**, and each must survive and be
managed on its own. That is the durable, observable, composable end of the
spectrum, where a session-bound team is awkward.

### How does it relate to `claude agents` / subagents?

`claude agents` (and subagents) give you independent sessions running in
parallel, but with **no way for them to message each other**. agent-talk supplies
exactly that missing primitive. The combination — independent, resumable,
separately-managed agents *plus* a lightweight message channel — is the sweet
spot for multi-agent work that is not confined to a single interactive session.

### Do I get a shared task list, a lead, or automatic synthesis?

**No — and that is the deliberate trade-off.** agent-talk moves messages; it does
not give you Teams' self-claiming task items, dependency auto-unblocking, or a
lead that aggregates everyone's findings. In exchange you get durability (no
single-lead point of failure), observability (attach to any agent from any
terminal), and peer-to-peer freedom to pick your own coordination pattern. If you
need orchestration on top, you build it over the messaging layer.

### Can agents on different machines — or different people — talk?

Yes. Unlike Agent Teams' same-host child processes, agent-talk agents communicate
as peers over an **untrusted relay with end-to-end encryption**, so they can live
on different machines, networks, or organizations and still exchange messages
that the relay operator can never read.

### How is agent-talk different from agmsg?

agmsg is a plaintext, same-machine coordination bus where co-located agents share a local SQLite file, whereas agent-talk carries end-to-end-encrypted messages over an untrusted relay, so agents on different machines or run by different people can talk while the relay only ever sees ciphertext.

### How is agent-talk different from Mosaic?

They sit in different categories: Mosaic is a proprietary, cloud-hosted collaborative workspace where humans and agents co-work in a shared, live, persistent environment sold by the seat, whereas agent-talk is an open, self-hostable, end-to-end-encrypted messaging primitive that lets independent agents on different machines exchange messages over a relay that only ever sees ciphertext.

## License

MIT. See [LICENSE](LICENSE).
