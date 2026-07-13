# agent-talk tests

`python -m unittest discover -s tests`

- **validate_plugin.py** — standalone deterministic validator (stdlib only, no
  LLM/network). Run as `python3 tests/validate_plugin.py`; exits non-zero with
  clear messages on any problem. Checks every `skills/*/SKILL.md` has `---`-
  delimited frontmatter with `name`/`description` where `name` equals the
  directory name; that `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`,
  and the root `package.json` (pi's manifest) are valid JSON with matching
  `version` and required fields (codex `skills` and pi `pi.skills` point at real
  dirs); that `marketplace.json` lists `agent-talk`; and that README/docs markdown
  fences and `<details>` tags are balanced. Run in CI by
  `.github/workflows/ci.yml`.
- **test_plugin.py** — static checks: manifests are valid JSON, every skill has
  frontmatter/description, expected skills present, `receive --all` only appears
  as a safety note, `bin/*.sh` pass `bash -n`. (no deps)
- **test_monitor.py** — `bin/inbox-monitor.sh` resolves this session's user from
  the session->user map and pushes new spool lines; idles safely without a
  session id. (no deps)
- **test_roundtrip.py** — a scoped `retalk receive --peer X --follow` follower
  feeds the per-user spool, against a local relay. **Opt-in:** runs only when `AGENT_TALK_E2E=1` and `retalk` is on PATH
  (so it stays out of CI, which guards the plugin's own artifacts). Run locally
  with `AGENT_TALK_E2E=1 python -m unittest discover -s tests`.

CI (`.github/workflows/ci.yml`) also has an **install-smoke** job that installs
the plugin on `codex`, `claude`, and `pi` and asserts all 14 skills are present:
codex/claude install from the checked-out marketplace and the job counts the
SKILL.md files in each agent's plugin cache; pi installs the repo with
`pi install <path>` (it discovers the `skills/` directory) and the job enumerates
skills via pi's RPC `get_commands`. All three installs are auth-free and make no
model calls (verified in a fresh, credential-free container), so the job needs no
secrets.

Not covered here (needs an interactive Claude Code session, not CI): plugin
*loading* / activation, monitor injection, AskUserQuestion flows,
`${CLAUDE_SESSION_ID}` substitution.
