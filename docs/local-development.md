# Local development

To run the plugin from a checkout instead of the published marketplace, start
Claude Code with the plugin directory:

```text
claude --plugin-dir /path/to/agent-talk
```

You can also register the checkout as a local marketplace entry from inside a
session:

```text
/plugin marketplace add ./agent-talk
```

Either way Claude Code reads your working copy, so edits to `skills/*/SKILL.md`
take effect the next time you run `/reload-plugins` or restart the session.
