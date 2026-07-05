from __future__ import annotations

from pathlib import Path

from . import Tool
from .bash import truncate


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def make_tools(config) -> list[Tool]:
    def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
        p = _resolve(path)
        if not p.exists():
            return f"Error: file not found: {p}. Check the path (use bash `ls` if unsure)."
        if p.is_dir():
            return f"Error: {p} is a directory. Use bash `ls` instead."
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            return f"Error: cannot read {p}: {e}"
        offset, limit = max(int(offset), 0), max(int(limit), 1)
        chunk = lines[offset:offset + limit]
        if not chunk:
            return f"(file has {len(lines)} lines; offset {offset} is out of range)"
        body = "\n".join(f"{i + offset + 1}\t{line}" for i, line in enumerate(chunk))
        if offset + limit < len(lines):
            body += f"\n[... {len(lines) - offset - limit} more lines, use offset={offset + limit}]"
        return truncate(body, config.tool_output_limit)

    def write_file(path: str, content: str) -> str:
        p = _resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {p}"

    def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        p = _resolve(path)
        if not p.exists():
            return f"Error: file not found: {p}"
        text = p.read_text(encoding="utf-8")
        count = text.count(old_string)
        if count == 0:
            return (
                "Error: old_string not found in the file. "
                "Call read_file first and copy the exact text including whitespace."
            )
        if count > 1 and not replace_all:
            return (
                f"Error: old_string appears {count} times. "
                "Include more surrounding lines to make it unique, or set replace_all=true."
            )
        new_text = text.replace(old_string, new_string) if replace_all \
            else text.replace(old_string, new_string, 1)
        p.write_text(new_text, encoding="utf-8")
        n = count if replace_all else 1
        return f"Replaced {n} occurrence(s) in {p}"

    return [
        Tool(
            name="read_file",
            description="Read a text file. Returns numbered lines. Use offset/limit for large files.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path."},
                    "offset": {"type": "integer", "description": "Line number to start from (0-based)."},
                    "limit": {"type": "integer", "description": "Max lines to read (default 2000)."},
                },
                "required": ["path"],
            },
            execute=read_file,
        ),
        Tool(
            name="write_file",
            description="Create or overwrite a file with the given content.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "File path to write."},
                    "content": {"type": "string", "description": "Full file content."},
                },
                "required": ["path", "content"],
            },
            execute=write_file,
            needs_approval=True,
        ),
        Tool(
            name="edit_file",
            description=(
                "Replace old_string with new_string in a file. "
                "old_string must match exactly and be unique unless replace_all=true."
            ),
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "File path to edit."},
                    "old_string": {"type": "string", "description": "Exact text to replace."},
                    "new_string": {"type": "string", "description": "Replacement text."},
                    "replace_all": {"type": "boolean", "description": "Replace every occurrence."},
                },
                "required": ["path", "old_string", "new_string"],
            },
            execute=edit_file,
            needs_approval=True,
        ),
    ]
