#!/usr/bin/env python3
"""Generate the Claude Code marketplace from the Codex marketplace.

Reads `.agents/plugins/marketplace.json` and each plugin's
`.codex-plugin/plugin.json`, and writes `.claude-plugin/marketplace.json`.
Run it again after syncing plugins from upstream; `--check` fails when the
committed file is stale.

Claude Code auto-discovers `skills/`, `commands/`, `agents/` and `.mcp.json`
in each plugin directory, so entries mostly carry metadata. MCP servers whose
Codex config does not work in Claude Code get a same-named inline override,
which replaces the `.mcp.json` definition.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
CODEX_MARKETPLACE_PATH = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

MARKETPLACE_NAME = "codex-plugins"
MARKETPLACE_OWNER = {"name": "OpenAI"}
MARKETPLACE_DESCRIPTION = (
    "Claude Code marketplace for the curated OpenAI Codex plugins in this repository."
)

# Remote plugins whose Claude Code package lives somewhere other than the Codex one.
SOURCE_OVERRIDES: dict[str, dict[str, str]] = {
    "qodo": {
        "source": "git-subdir",
        "url": "https://github.com/qodo-ai/qodo-skills.git",
        "path": "packages/qodo",
    },
}

# Codex-only MCP server keys that Claude Code ignores.
CODEX_ONLY_MCP_KEYS = {
    "bearer_token_env_var",
    "cwd",
    "description",
    "env_vars",
    "icons",
    "note",
    "oauth",
    "oauth_resource",
    "scopes",
    "title",
    "tool_timeout_sec",
}

MANIFEST_METADATA_KEYS = ("description", "version", "author", "homepage", "repository", "license", "keywords")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def has_claude_components(plugin_dir: Path) -> bool:
    """True when Claude Code can load anything from the plugin (ChatGPT apps can't)."""
    return (
        (plugin_dir / "skills").is_dir()
        or any((plugin_dir / "commands").glob("*.md"))
        or any((plugin_dir / "agents").glob("*.md"))
        or (plugin_dir / ".mcp.json").is_file()
    )


def to_plugin_root(value: str) -> str:
    if value.startswith("./"):
        return "${CLAUDE_PLUGIN_ROOT}/" + value[2:]
    return value


def claude_mcp_override(server: dict[str, Any]) -> dict[str, Any] | None:
    """Return a Claude Code config for a Codex MCP server, or None if it works as-is.

    Claude Code starts plugin stdio servers in the session's working directory,
    so plugin-relative paths must be anchored to ${CLAUDE_PLUGIN_ROOT}.
    """
    command = server.get("command")
    args = server.get("args", [])
    relative_paths = [value for value in [command, *args] if isinstance(value, str) and value.startswith("./")]
    bearer_env = server.get("bearer_token_env_var")
    if not relative_paths and not bearer_env:
        return None

    override = {key: value for key, value in server.items() if key not in CODEX_ONLY_MCP_KEYS}
    if command is not None:
        override["command"] = to_plugin_root(command)
    if args:
        override["args"] = [to_plugin_root(arg) if isinstance(arg, str) else arg for arg in args]
    if bearer_env:
        override["headers"] = {**override.get("headers", {}), "Authorization": f"Bearer ${{{bearer_env}}}"}
    return override


def local_entry(codex_entry: dict[str, Any]) -> dict[str, Any] | None:
    source_path = codex_entry["source"]["path"]
    plugin_dir = REPO_ROOT / source_path
    if not has_claude_components(plugin_dir):
        return None

    manifest = load_json(plugin_dir / ".codex-plugin" / "plugin.json")
    entry: dict[str, Any] = {"name": codex_entry["name"], "source": source_path}
    display_name = manifest.get("interface", {}).get("displayName")
    if display_name:
        entry["displayName"] = display_name
    for key in MANIFEST_METADATA_KEYS:
        if manifest.get(key):
            entry[key] = manifest[key]
    if codex_entry.get("category"):
        entry["category"] = codex_entry["category"]

    mcp_path = plugin_dir / ".mcp.json"
    if mcp_path.is_file():
        overrides = {}
        for server_name, server in load_json(mcp_path).get("mcpServers", {}).items():
            override = claude_mcp_override(server)
            if override is not None:
                overrides[server_name] = override
        if overrides:
            entry["mcpServers"] = overrides
    return entry


def remote_entry(codex_entry: dict[str, Any]) -> dict[str, Any]:
    name = codex_entry["name"]
    entry: dict[str, Any] = {"name": name, "source": SOURCE_OVERRIDES.get(name, codex_entry["source"])}
    display_name = codex_entry.get("interface", {}).get("displayName")
    if display_name:
        entry["displayName"] = display_name
    if codex_entry.get("category"):
        entry["category"] = codex_entry["category"]
    return entry


def build_marketplace() -> tuple[dict[str, Any], list[str]]:
    plugins = []
    skipped = []
    for codex_entry in load_json(CODEX_MARKETPLACE_PATH)["plugins"]:
        if codex_entry["source"]["source"] == "local":
            entry = local_entry(codex_entry)
            if entry is None:
                skipped.append(codex_entry["name"])
                continue
        else:
            entry = remote_entry(codex_entry)
        plugins.append(entry)

    marketplace = {
        "name": MARKETPLACE_NAME,
        "owner": MARKETPLACE_OWNER,
        "description": MARKETPLACE_DESCRIPTION,
        "plugins": plugins,
    }
    return marketplace, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the committed marketplace is stale")
    args = parser.parse_args()

    marketplace, skipped = build_marketplace()
    content = json.dumps(marketplace, indent=2, ensure_ascii=False) + "\n"
    relative_path = CLAUDE_MARKETPLACE_PATH.relative_to(REPO_ROOT)

    if args.check:
        current = CLAUDE_MARKETPLACE_PATH.read_text(encoding="utf-8") if CLAUDE_MARKETPLACE_PATH.exists() else None
        if current != content:
            print(f"{relative_path} is stale; run scripts/generate_claude_marketplace.py", file=sys.stderr)
            return 1
        print(f"{relative_path} is up to date")
        return 0

    CLAUDE_MARKETPLACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLAUDE_MARKETPLACE_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {relative_path} with {len(marketplace['plugins'])} plugins")
    if skipped:
        print(f"Skipped (no Claude Code components, e.g. ChatGPT app only): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
