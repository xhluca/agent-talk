# Contributing

Thanks for contributing to agent-talk. Keep pull requests small and focused,
one topic per branch.

## Ground rules

- **Disclose AI-generated code.** If any part of your change was produced by
  an AI tool, say so clearly in the pull request description: which tool, and
  which parts. You must have reviewed and understood every line you submit,
  and you take responsibility for it. Undisclosed AI-generated code will get
  the pull request closed.
- **Tests.** Bug fixes need a regression test. Run
  `python3 tests/validate_plugin.py` before pushing; CI must be green to
  merge.
- **No secrets or personal data.** Never commit tokens, keys, identities,
  inboxes, or real fingerprints. Scrub demo recordings (names, emails, paths)
  before adding them.
- **Docs.** Write plain, natural English. Keep skill files
  (`skills/*/SKILL.md`) consistent with the existing format, and update the
  README when behavior changes.

## Workflow

1. Branch or fork, then open a pull request with a clear description of what
   changed and why.
2. CI runs plugin validation and install smokes for all six supported hosts;
   all checks must pass.
3. A maintainer reviews and squash-merges.
