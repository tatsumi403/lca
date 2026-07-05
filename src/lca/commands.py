"""スラッシュコマンド。

- ビルトイン: /help /clear /compact /skills /tools /quit
- スキル明示呼び出し: /<skill名> [引数] → SKILL.md本文を展開したuserメッセージに変換
- カスタムコマンド: ~/.lca/commands/*.md, ./.lca/commands/*.md ($ARGUMENTS 置換のみ)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import GLOBAL_DIR, PROJECT_DIR_NAME
from .skills import Skill


@dataclass
class Dispatch:
    kind: str          # "builtin" | "prompt" | "unknown" | "not_command"
    action: str = ""   # builtin名
    prompt: str = ""   # モデルに送るuserメッセージ


def load_custom_commands(cwd: Path | None = None) -> dict[str, Path]:
    cwd = cwd or Path.cwd()
    commands: dict[str, Path] = {}
    for base in (GLOBAL_DIR / "commands", cwd / PROJECT_DIR_NAME / "commands"):
        if base.is_dir():
            for md in sorted(base.glob("*.md")):
                commands[md.stem] = md
    return commands


BUILTINS = {"help", "clear", "compact", "skills", "tools", "quit", "exit"}


def dispatch(line: str, skills: dict[str, Skill], commands: dict[str, Path]) -> Dispatch:
    if not line.startswith("/"):
        return Dispatch(kind="not_command")
    name, _, args = line[1:].partition(" ")
    args = args.strip()
    if name in BUILTINS:
        return Dispatch(kind="builtin", action="quit" if name == "exit" else name)
    if name in skills:
        body = skills[name].body()
        prompt = f"以下のスキル指示に従ってタスクを実行してください。\n\n{body}"
        if args:
            prompt += f"\n\n引数: {args}"
        return Dispatch(kind="prompt", prompt=prompt)
    if name in commands:
        template = commands[name].read_text(encoding="utf-8")
        return Dispatch(kind="prompt", prompt=template.replace("$ARGUMENTS", args))
    return Dispatch(kind="unknown", action=name)


HELP_TEXT = """\
[bold]ビルトインコマンド[/bold]
  /help      このヘルプ
  /skills    利用可能なスキル一覧
  /tools     ツール一覧
  /compact   会話履歴をLLMで要約して圧縮
  /clear     会話履歴をクリア
  /quit      終了 (Ctrl+D でも可)

[bold]スキル / カスタムコマンド[/bold]
  /<スキル名> [引数]   スキルを明示的に実行
  /<コマンド名> [引数] ~/.lca/commands/*.md を実行 ($ARGUMENTS 置換)\
"""
