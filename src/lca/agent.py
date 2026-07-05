"""エージェントループ本体。"""

from __future__ import annotations

from rich.console import Console

from .history import History, estimate_tokens
from .llm import LLM, ToolCall
from .permissions import Permissions
from .tools import ToolRegistry

DENIED_RESULT = "User denied this action. Ask the user what to do instead."
MAX_SAME_ERROR = 3


class Agent:
    def __init__(self, llm: LLM, registry: ToolRegistry, permissions: Permissions,
                 history: History, console: Console, config):
        self.llm = llm
        self.registry = registry
        self.permissions = permissions
        self.history = history
        self.console = console
        self.config = config
        self.system_prompt = ""  # cli側で構築して設定する

    def run_turn(self, user_input: str) -> None:
        self.history.append({"role": "user", "content": user_input})
        system_tokens = estimate_tokens(self.system_prompt)
        last_error = ""
        error_streak = 0

        for _ in range(self.config.max_steps):
            self.history.enforce_budget(self.config.num_ctx, system_tokens)
            messages = [{"role": "system", "content": self.system_prompt}, *self.history.messages]
            try:
                result = self.llm.chat_stream(
                    messages,
                    tools=self.registry.schemas(),
                    on_token=self._on_token,
                )
            except KeyboardInterrupt:
                self.console.print("\n[yellow]中断しました[/yellow]")
                return
            finally:
                self._end_stream()

            self.history.calibrate(result.prompt_tokens, system_tokens)
            self.history.append({
                "role": "assistant",
                "content": result.text,
                **({"tool_calls": [tc.as_message_dict() for tc in result.tool_calls]}
                   if result.tool_calls else {}),
            })

            if not result.tool_calls:
                return  # テキストで完結 → ユーザーに制御を返す

            for call in result.tool_calls:
                output = self._run_tool(call)
                self.history.append({
                    "role": "tool",
                    "tool_name": call.name,
                    "content": output,
                })
                if output.startswith("Error:"):
                    if output == last_error:
                        error_streak += 1
                    else:
                        last_error, error_streak = output, 1
                    if error_streak >= MAX_SAME_ERROR:
                        self.console.print(
                            "[red]同じエラーが続いたため中断します。指示を変えて再試行してください。[/red]")
                        return
                else:
                    last_error, error_streak = "", 0

        self.console.print(f"[yellow]ステップ上限 ({self.config.max_steps}) に達したため中断しました[/yellow]")

    # ---- internals ----

    def _run_tool(self, call: ToolCall) -> str:
        tool = self.registry.get(call.name)
        if tool is None:
            return (f"Error: unknown tool '{call.name}'. "
                    f"Available tools: {self.registry.names()}.")
        args = tool.normalize_args(call.arguments)
        error = tool.validate(args)
        if error:
            self.console.print(f"[red]✗ {call.name}: 引数エラー[/red]")
            return error

        self._show_call(call.name, args)
        if not self._approve(call.name, args):
            self.console.print("[yellow]→ 拒否[/yellow]")
            return DENIED_RESULT
        try:
            with self.console.status(f"[dim]{call.name} 実行中...[/dim]"):
                result = tool.execute(**args)
        except KeyboardInterrupt:
            return "Error: interrupted by user."
        except Exception as e:  # ツール内部の想定外エラーもモデルに返す
            return f"Error: tool '{call.name}' failed: {e}"
        self._show_result(result)
        return result

    def _approve(self, name: str, args: dict) -> bool:
        tool = self.registry.get(name)
        if not tool or not tool.needs_approval:
            return True
        if name == "bash":
            return self.permissions.approve_bash(args.get("command", ""))
        if name == "write_file":
            return self.permissions.approve_write(args.get("path", ""), args.get("content", ""))
        if name == "edit_file":
            return self.permissions.approve_edit(
                args.get("path", ""), args.get("old_string", ""), args.get("new_string", ""))
        return True

    def _show_call(self, name: str, args: dict) -> None:
        if name == "bash":
            summary = args.get("command", "")
        elif name == "ask_user":
            summary = ""
        else:
            summary = str(args.get("path", ""))
        if len(summary) > 120:
            summary = summary[:120] + "…"
        self.console.print(f"[bold blue]⏺ {name}[/bold blue] [dim]{summary}[/dim]")

    def _show_result(self, result: str) -> None:
        lines = result.splitlines() or [""]
        head = lines[0][:100]
        suffix = f" (+{len(lines) - 1} lines)" if len(lines) > 1 else ""
        style = "red" if result.startswith("Error:") else "dim"
        self.console.print(f"  [{style}]⎿ {head}{suffix}[/{style}]")

    # ストリーミング表示: 本文は素で、thinkは薄色で流す
    _streamed = False

    def _on_token(self, text: str, is_thinking: bool) -> None:
        self._streamed = True
        if is_thinking:
            self.console.print(text, style="grey50", end="", highlight=False)
        else:
            self.console.print(text, end="", highlight=False)

    def _end_stream(self) -> None:
        if self._streamed:
            self.console.print()
            self._streamed = False
