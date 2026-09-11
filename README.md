# Plugins

This repository contains a curated collection of Codex plugin examples.

Each plugin lives under `plugins/<name>/` with a required
`.codex-plugin/plugin.json` manifest and optional companion surfaces such as
`skills/`, `.app.json`, `.mcp.json`, plugin-level `agents/`, `commands/`,
`hooks.json`, `assets/`, and other supporting files.

The default marketplace lives at `.agents/plugins/marketplace.json` and points
at the standard `plugins/` directory. API key login users have a separate
marketplace at `.agents/plugins/api_marketplace.json`.

Highlighted richer examples in this repo include:

- `plugins/figma` for `use_figma`, Code to Canvas, Code Connect, and design system rules
- `plugins/notion` for planning, research, meetings, and knowledge capture
- `plugins/build-ios-apps` for SwiftUI implementation, refactors, performance, and debugging
- `plugins/build-macos-apps` for macOS SwiftUI/AppKit workflows, build/run/debug loops, and packaging guidance
- `plugins/build-web-apps` for deployment, UI, payments, and database workflows
- `plugins/expo` for Expo and React Native apps, SDK upgrades, EAS workflows, and Codex Run actions
- `plugins/netlify`, `plugins/remotion`, and `plugins/google-slides` for additional public skill- and MCP-backed plugin bundles

## Claude Code

`.claude-plugin/marketplace.json` exposes the same plugins as a Claude Code
marketplace named `codex-plugins`:

```
/plugin marketplace add <path-or-github-repo>
/plugin install linear@codex-plugins
```

The file is generated from `.agents/plugins/marketplace.json` and the
`.codex-plugin/plugin.json` manifests. Regenerate it after syncing plugins:

```
python3 scripts/generate_claude_marketplace.py
python3 scripts/generate_claude_marketplace.py --check  # fails if stale
```

Claude Code auto-discovers each plugin's `skills/`, `commands/`, `agents/*.md`,
and `.mcp.json`. The generator adds inline MCP overrides where the Codex config
doesn't work in Claude Code: stdio servers get `${CLAUDE_PLUGIN_ROOT}`-anchored
paths, and `bearer_token_env_var` becomes an `Authorization` header.

Limitations:

- ChatGPT apps (`.app.json`) have no Claude Code equivalent. Plugins that only
  ship an app (lovable, outlook-calendar, outlook-email, sharepoint, teams) are
  left out.
- Remote MCP servers use Claude Code's OAuth flow. Servers without dynamic
  client registration won't authenticate (Zoom confirmed; likely also the
  Google servers, whose Codex config uses placeholder client IDs).
- The GitHub MCP server needs `GITHUB_PAT_TOKEN` set.
- Some skills and commands reference Codex-specific tooling.
