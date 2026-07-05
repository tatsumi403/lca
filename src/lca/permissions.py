"""ツール実行の承認フロー。

- bash: denylist(正規表現)即拒否 → allowlist(プレフィックス)自動許可 → y/n/a/A プロンプト
- write_file/edit_file: diff/内容プレビュー付きで y/n/a プロンプト。cwd外は警告強調
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from rich.panel import Panel
from rich.syntax import Syntax

from . import config as config_mod


class Permissions:
    def __init__(self, config, console):
        self.config = config
        self.console = console
        self.session_bash_allow: list[str] = []
        self.session_file_allow = False

    # ---- bash ----

    def _denied(self, command: str) -> bool:
        return any(re.search(pattern, command) for pattern in self.config.bash_denylist)

    def _allowed(self, command: str) -> bool:
        cmd = command.strip()
        return any(
            cmd == prefix or cmd.startswith(prefix + " ")
            for prefix in (*self.config.bash_allowlist, *self.session_bash_allow)
        )

    def approve_bash(self, command: str) -> bool:
        if self._denied(command):
            self.console.print("[red]✗ denylist に該当するため拒否しました[/red]")
            return False
        if self._allowed(command):
            return True
        self.console.print(Panel(command, title="bash", border_style="yellow"))
        choice = self._prompt("[y]es / [n]o / [a]lways(session) / [A]lways(save)")
        if choice in ("y", "yes"):
            return True
        prefix = " ".join(command.strip().split()[:2]) or command.strip()
        if choice == "a":
            self.session_bash_allow.append(prefix)
            return True
        if choice == "A":
            self.session_bash_allow.append(prefix)
            config_mod.save_allowlist_entry(prefix)
            self.console.print(f"[dim]allowlist に保存: {prefix}[/dim]")
            return True
        return False

    # ---- file writes ----

    def approve_write(self, path: str, content: str) -> bool:
        if self.session_file_allow:
            return True
        p = Path(path).expanduser().resolve()
        exists = p.exists()
        title = f"write_file: {p} ({'上書き' if exists else '新規'})"
        if exists:
            old = p.read_text(encoding="utf-8", errors="replace")
            preview = _diff(old, content, str(p))
        else:
            preview = Syntax(_head(content), _lexer(p), line_numbers=False)
        return self._approve_file(p, title, preview)

    def approve_edit(self, path: str, old_string: str, new_string: str) -> bool:
        if self.session_file_allow:
            return True
        p = Path(path).expanduser().resolve()
        return self._approve_file(p, f"edit_file: {p}", _diff(old_string, new_string, str(p)))

    def _approve_file(self, p: Path, title: str, preview) -> bool:
        border = "yellow"
        try:
            p.relative_to(Path.cwd())
        except ValueError:
            self.console.print(f"[bold red]警告: 作業ディレクトリ外への書き込みです: {p}[/bold red]")
            border = "red"
        self.console.print(Panel(preview, title=title, border_style=border))
        choice = self._prompt("[y]es / [n]o / [a]ll file edits this session")
        if choice == "a":
            self.session_file_allow = True
            return True
        return choice in ("y", "yes")

    def _prompt(self, options: str) -> str:
        try:
            return self.console.input(f"[bold]実行しますか? {options}: [/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            return "n"


def _head(text: str, lines: int = 30) -> str:
    parts = text.splitlines()
    if len(parts) <= lines:
        return text
    return "\n".join(parts[:lines]) + f"\n... (+{len(parts) - lines} lines)"


def _lexer(path: Path) -> str:
    return {"py": "python", "js": "javascript", "ts": "typescript", "sh": "bash",
            "md": "markdown", "json": "json", "toml": "toml", "yaml": "yaml",
            "yml": "yaml"}.get(path.suffix.lstrip("."), "text")


def _diff(old: str, new: str, name: str) -> Syntax:
    diff = "\n".join(difflib.unified_diff(
        old.splitlines(), new.splitlines(),
        fromfile=f"a/{name}", tofile=f"b/{name}", lineterm="",
    ))
    return Syntax(_head(diff, 60), "diff", line_numbers=False)
