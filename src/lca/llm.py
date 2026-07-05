"""Ollama クライアントの薄ラッパ。

- streaming + tools の同時利用
- <think> ブロックの表示/履歴分離
- ツールコールをプレーンテキストJSONで吐くモデルへのフォールバックパース
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

import ollama

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


@dataclass
class ToolCall:
    name: str
    arguments: dict

    def as_message_dict(self) -> dict:
        return {"function": {"name": self.name, "arguments": self.arguments}}


@dataclass
class ChatResult:
    text: str                       # think除去済み（履歴保存用）
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int | None = None  # ollamaのprompt_eval_count（トークン概算の補正用）


class LLM:
    def __init__(self, host: str, model: str, num_ctx: int):
        self.client = ollama.Client(host=host)
        self.model = model
        self.num_ctx = num_ctx

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        on_token: Callable[[str, bool], None] | None = None,
    ) -> ChatResult:
        """ストリーミングでチャットする。

        on_token(text, is_thinking) が逐次呼ばれる。戻り値のtextはthink除去済み。
        """
        stream = self.client.chat(
            model=self.model,
            messages=messages,
            tools=tools or None,
            stream=True,
            options={"num_ctx": self.num_ctx},
        )
        full_text = ""
        tool_calls: list[ToolCall] = []
        prompt_tokens = None
        in_think = False
        for chunk in stream:
            msg = chunk.get("message", {})
            content = msg.get("content") or ""
            # ollama 0.9+ はqwen3等のthinkingを別フィールドで返すことがある
            thinking = msg.get("thinking") or ""
            if thinking and on_token:
                on_token(thinking, True)
            if content:
                full_text += content
                if on_token:
                    # <think>ブロックの区間判定（チャンク跨ぎ対応の簡易版）
                    for piece, is_think in _split_think(content, in_think):
                        if piece:
                            on_token(piece, is_think)
                    in_think = _update_think_state(full_text)
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"_raw": args}
                tool_calls.append(ToolCall(name=fn.get("name", ""), arguments=dict(args)))
            if chunk.get("done"):
                prompt_tokens = chunk.get("prompt_eval_count")

        clean = THINK_RE.sub("", full_text).strip()
        if not tool_calls:
            fallback = parse_textual_tool_call(clean)
            if fallback is not None:
                tool_calls = [fallback]
                clean = ""
        return ChatResult(text=clean, tool_calls=tool_calls, prompt_tokens=prompt_tokens)


def _update_think_state(full_text: str) -> bool:
    opens = full_text.count("<think>")
    closes = full_text.count("</think>")
    return opens > closes


def _split_think(content: str, in_think: bool) -> list[tuple[str, bool]]:
    """チャンクを <think> 境界で分割し (テキスト片, thinkか) を返す簡易実装。"""
    pieces: list[tuple[str, bool]] = []
    rest = content
    state = in_think
    while rest:
        tag = "</think>" if state else "<think>"
        idx = rest.find(tag)
        if idx == -1:
            pieces.append((rest, state))
            break
        pieces.append((rest[:idx], state))
        rest = rest[idx + len(tag):]
        state = not state
    return pieces


def parse_textual_tool_call(text: str) -> ToolCall | None:
    """応答全体がツールコール様のJSONだけの場合に救済パースする。

    例: {"name": "bash", "arguments": {"command": "ls"}}
        {"tool": "read_file", "parameters": {"path": "a.py"}}
    """
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", candidate).strip()
    if not (candidate.startswith("{") and candidate.endswith("}")):
        return None
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name") or data.get("tool") or data.get("tool_name")
    args = data.get("arguments") or data.get("parameters") or data.get("args")
    if isinstance(name, str) and isinstance(args, dict):
        return ToolCall(name=name, arguments=args)
    return None
