"""ツールレジストリ。

v2でMCPツールを動的登録できるよう、dictベースのレジストリに統一しておく。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# ローカルモデルがよく間違える引数名を正規名へ吸収する
ARG_ALIASES = {
    "file_path": "path",
    "filepath": "path",
    "filename": "path",
    "file": "path",
    "cmd": "command",
    "text": "content",
    "old_str": "old_string",
    "new_str": "new_string",
    "old": "old_string",
    "new": "new_string",
}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict                      # JSON Schema (properties/required)
    execute: Callable[..., str]           # kwargs -> result text
    needs_approval: bool = False

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters.get("properties", {}),
                    "required": self.parameters.get("required", []),
                },
            },
        }

    def normalize_args(self, args: dict) -> dict:
        props = self.parameters.get("properties", {})
        out = {}
        for key, value in args.items():
            key = ARG_ALIASES.get(key, key)
            if key in props:
                out[key] = value
        return out

    def validate(self, args: dict) -> str | None:
        """問題があればエラーメッセージ（英語、モデル向け）を返す。"""
        props = self.parameters.get("properties", {})
        missing = [r for r in self.parameters.get("required", []) if r not in args]
        if missing:
            return (
                f"Error: missing required argument(s) {missing} for tool '{self.name}'. "
                f"Expected arguments: {list(props)}. Fix the arguments and retry."
            )
        return None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]


def build_registry(config, console) -> ToolRegistry:
    from . import ask_user, bash, files

    registry = ToolRegistry()
    registry.register(bash.make_tool(config))
    for tool in files.make_tools(config):
        registry.register(tool)
    registry.register(ask_user.make_tool(console))
    return registry
