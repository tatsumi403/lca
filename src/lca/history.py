"""会話履歴の保持とコンテキスト予算の強制。

トークンは len(text)//3 の保守的な近似で概算し、直近応答の prompt_eval_count で補正する。
予算超過時: ①古いツール出力を [elided] 化 → ②最古のターンから削除（直近は常に保持）。
"""

from __future__ import annotations

ELIDED = "[tool output elided to save context]"
KEEP_RECENT = 6           # 直近Nメッセージは絶対に触らない
OUTPUT_HEADROOM = 2048    # モデル出力用に空けておくトークン


def estimate_tokens(text: str) -> int:
    return len(text) // 3 + 1


class History:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self._correction = 1.0  # 実測prompt_eval_countによる補正係数

    def append(self, message: dict) -> None:
        self.messages.append(message)

    def clear(self) -> None:
        self.messages = []

    def estimate(self, extra: str = "") -> int:
        total = sum(estimate_tokens(str(m.get("content", ""))) for m in self.messages)
        return int((total + estimate_tokens(extra)) * self._correction)

    def calibrate(self, prompt_tokens: int | None, system_len: int) -> None:
        if not prompt_tokens:
            return
        estimated = self.estimate() + system_len
        if estimated > 0:
            # 急激な補正を避けるためクランプ
            self._correction = min(max(prompt_tokens / estimated, 0.5), 3.0) * 0.5 \
                + self._correction * 0.5

    def enforce_budget(self, num_ctx: int, system_tokens: int) -> None:
        budget = num_ctx - system_tokens - OUTPUT_HEADROOM
        if budget <= 0:
            return
        # ① 古いツール出力を elide
        for msg in self.messages[:-KEEP_RECENT]:
            if self.estimate() <= budget:
                return
            if msg.get("role") == "tool" and msg.get("content") != ELIDED:
                msg["content"] = ELIDED
        # ② 最古から削除
        while self.estimate() > budget and len(self.messages) > KEEP_RECENT:
            self.messages.pop(0)
        # 先頭が tool メッセージにならないよう整える
        while self.messages and self.messages[0].get("role") == "tool":
            self.messages.pop(0)

    def compact(self, llm) -> str:
        """履歴をLLMで要約し [要約 + 直近2メッセージ] に置き換える。要約文を返す。"""
        if not self.messages:
            return "(履歴が空です)"
        transcript = []
        for m in self.messages:
            role = m.get("role", "?")
            content = str(m.get("content", ""))[:2000]
            transcript.append(f"[{role}] {content}")
        summary_prompt = (
            "Summarize the working session below for continuing later. Include: "
            "the goal, files changed, key decisions, and unfinished tasks. "
            "Answer in the user's language.\n\n" + "\n".join(transcript)
        )
        result = llm.chat_stream([{"role": "user", "content": summary_prompt}])
        tail = [m for m in self.messages[-2:] if m.get("role") != "tool"]
        self.messages = [
            {"role": "user", "content": f"(前回までの作業要約)\n{result.text}"},
            *tail,
        ]
        return result.text
