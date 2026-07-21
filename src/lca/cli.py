"""REPL 本体 + 一発実行モード。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import ollama
from rich.console import Console

from . import __version__, commands
from .agent import Agent
from .config import load_config
from .history import History
from .llm import LLM
from .permissions import Permissions
from .prompt import build_system_prompt
from .skills import load_skills
from .tools import build_registry


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lca",
        description="Local Coding Agent — Ollama で動くローカルコーディングエージェント",
    )
    parser.add_argument(
        "-C", "--dir", metavar="DIR",
        help="起動前に移動する作業ディレクトリ（設定・スキル・指示ファイル・相対パスの基準）",
    )
    parser.add_argument(
        "-p", "--prompt", metavar="TEXT",
        help="指示を1ターンだけ実行して終了する（REPLに入らない）",
    )
    parser.add_argument(
        "prompt_args", nargs="*",
        help="位置引数として渡す指示（-p の代わり）",
    )
    parser.add_argument("-V", "--version", action="version", version=f"lca {__version__}")
    return parser.parse_args(argv)


def _resolve_oneshot(prompt: str | None, prompt_args: list[str]) -> str | None:
    """一発実行する指示を決める。-p 優先、なければ位置引数を連結。無ければ None（REPL）。"""
    if prompt:
        return prompt
    joined = " ".join(prompt_args).strip()
    return joined or None


def main() -> None:
    args = _parse_args()
    if args.dir:
        try:
            os.chdir(args.dir)
        except OSError as e:
            print(f"cd 失敗: {args.dir}: {e}", file=sys.stderr)
            sys.exit(1)

    console = Console()
    cwd = Path.cwd()
    config = load_config(cwd)

    llm = LLM(host=config.ollama_host, model=config.model, num_ctx=config.num_ctx)
    if not _check_ollama(llm, console, config):
        sys.exit(1)

    skills = load_skills(cwd)
    custom_commands = commands.load_custom_commands(cwd)
    registry = build_registry(config, console)
    history = History()
    permissions = Permissions(config, console)
    agent = Agent(llm, registry, permissions, history, console, config)
    agent.system_prompt = build_system_prompt(config, skills, cwd)

    def process(line: str) -> bool:
        """1行の入力を処理する。REPLを続けるなら True、終了なら False。"""
        d = commands.dispatch(line, skills, custom_commands)
        if d.kind == "builtin":
            if d.action == "quit":
                return False
            _run_builtin(d.action, console, history, llm, skills, registry)
            return True
        if d.kind == "unknown":
            console.print(f"[red]不明なコマンド: /{d.action}[/red] (/help 参照)")
            return True
        prompt = d.prompt if d.kind == "prompt" else line
        try:
            agent.run_turn(prompt)
        except KeyboardInterrupt:
            console.print("\n[yellow]中断しました[/yellow]")
        except ollama.ResponseError as e:
            console.print(f"[red]Ollama エラー: {e.error}[/red]")
        return True

    # 一発実行モード: -p か位置引数があれば1ターン実行して終了（バナー等のREPL演出は出さない）
    oneshot = _resolve_oneshot(args.prompt, args.prompt_args)
    if oneshot is not None:
        process(oneshot)
        return

    console.print(
        f"[bold]lca[/bold] v{__version__}  "
        f"[dim]model={config.model} num_ctx={config.num_ctx} "
        f"skills={len(skills)} cwd={cwd}[/dim]"
    )
    console.print("[dim]/help でコマンド一覧、Ctrl+D で終了[/dim]\n")
    while True:
        try:
            line = console.input("[bold green]› [/bold green]").strip()
        except EOFError:
            break
        except KeyboardInterrupt:
            console.print("[dim](Ctrl+D で終了)[/dim]")
            continue
        if not line:
            continue
        if not process(line):
            break
        console.print()

    console.print("[dim]bye[/dim]")


def _run_builtin(action: str, console: Console, history: History, llm, skills, registry) -> None:
    if action == "help":
        console.print(commands.HELP_TEXT)
    elif action == "clear":
        history.clear()
        console.print("[dim]履歴をクリアしました[/dim]")
    elif action == "compact":
        with console.status("[dim]要約中...[/dim]"):
            summary = history.compact(llm)
        console.print(f"[dim]圧縮しました。要約:[/dim]\n{summary}")
    elif action == "skills":
        if not skills:
            console.print("[dim]スキルはありません (~/.lca/skills/<name>/SKILL.md に配置)[/dim]")
        for s in skills.values():
            console.print(f"[bold]{s.name}[/bold]: {s.description}\n  [dim]{s.path}[/dim]")
    elif action == "tools":
        for name in registry.names():
            console.print(f"- {name}")


def _check_ollama(llm: LLM, console: Console, config) -> bool:
    try:
        models = [m.model for m in llm.client.list().models]
    except Exception:
        console.print(
            f"[red]Ollama に接続できません ({config.ollama_host})[/red]\n"
            "起動していますか? → [bold]ollama serve[/bold] または "
            "[bold]brew services start ollama[/bold]"
        )
        return False
    if not any(m == config.model or m.startswith(config.model + ":") for m in models):
        console.print(
            f"[yellow]モデル {config.model} が見つかりません。[/yellow]\n"
            f"→ [bold]ollama pull {config.model}[/bold]\n"
            f"インストール済み: {', '.join(models) or '(なし)'}"
        )
        return False
    return True


if __name__ == "__main__":
    main()
