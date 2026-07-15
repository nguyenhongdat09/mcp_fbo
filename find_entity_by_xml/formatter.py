"""Format entity lookup results for MCP agent response."""

from __future__ import annotations

from typing import Any


def format_entity_result(result: dict[str, Any]) -> str:
    if not result.get("success"):
        lines = [f"[ERROR] {result.get('error', 'Unknown error')}"]
        if result.get("file_path"):
            lines.append(f"File: {result['file_path']}")
        if result.get("mode"):
            lines.append(f"Mode: {', '.join(result['mode'])}")
        return "\n".join(lines)

    modes = result.get("mode") or ["content"]
    lines = [
        "[OK] XML entities",
        f"File: {result.get('file_path', '')}",
        f"Mode: {', '.join(modes)}",
    ]
    if result.get("entity_count") is not None:
        lines.append(f"Entities in DTD: {result['entity_count']}")
    if result.get("reloaded") is not None:
        lines.append(f"Force reload: {'yes' if result['reloaded'] else 'no'}")

    if result.get("list_all"):
        names = result.get("entity_names") or []
        lines.append(f"Total entities: {len(names)}")
        lines.append("")
        for name in names:
            lines.append(f"  - {name}")

    entities_out = result.get("entities") or []
    if entities_out:
        found_count = sum(1 for item in entities_out if item.get("found"))
        lines.append(f"Content — requested: {len(entities_out)}, found: {found_count}")
        lines.append("")

        for item in entities_out:
            name = item.get("name", "")
            lines.append(f"--- {name} (content) ---")
            if item.get("found"):
                content = item.get("content", "")
                lines.append("```xml")
                lines.append(content.rstrip())
                lines.append("```")
            else:
                lines.append("[NOT FOUND]")
                if item.get("hint"):
                    lines.append(item["hint"])
            lines.append("")

    path_out = result.get("entity_paths") or []
    if path_out:
        found_count = sum(1 for item in path_out if item.get("found"))
        lines.append(f"Path — requested: {len(path_out)}, found: {found_count}")
        lines.append("")

        for item in path_out:
            name = item.get("name", "")
            lines.append(f"--- {name} (path) ---")
            if item.get("found"):
                source_file = item.get("source_file", "")
                line = item.get("line", -1)
                lines.append(f"Source: {source_file}:{line}")
                watch_files = item.get("watch_files") or []
                if watch_files:
                    lines.append("Watch files:")
                    for watch_file in watch_files:
                        lines.append(f"  - {watch_file}")
            else:
                lines.append("[NOT FOUND]")
                if item.get("hint"):
                    lines.append(item["hint"])
            lines.append("")

    return "\n".join(lines).rstrip()
