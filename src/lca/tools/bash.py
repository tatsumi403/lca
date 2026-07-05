from __future__ import annotations

import subprocess

from . import Tool


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    dropped = text[limit:].count("\n") + 1
    return f"{cut}\n[... truncated {dropped} lines]"


def make_tool(config) -> Tool:
    def execute(command: str, timeout: int = 120) -> str:
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=min(int(timeout), 600),
            )
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout}s"
        out = proc.stdout or ""
        if proc.stderr:
            out += ("\n" if out else "") + f"[stderr]\n{proc.stderr}"
        if proc.returncode != 0:
            out += ("\n" if out else "") + f"[exit code: {proc.returncode}]"
        return truncate(out, config.tool_output_limit) or "(no output)"

    return Tool(
        name="bash",
        description=(
            "Run a shell command and return its stdout/stderr. "
            "Use this for listing files, searching (grep), git, and running programs."
        ),
        parameters={
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute."},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)."},
            },
            "required": ["command"],
        },
        execute=execute,
        needs_approval=True,
    )
