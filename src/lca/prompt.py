"""システムプロンプトの組み立て。

内部固定文言は英語（トークン節約 + tool call 精度）。ユーザーが書く
指示ファイル・スキルは日本語のままでよい。
"""

from __future__ import annotations

from pathlib import Path

from .config import GLOBAL_DIR, Config
from .history import estimate_tokens
from .skills import Skill, skills_prompt_section

BASE_PROMPT = """\
You are a coding agent running in a terminal on the user's machine \
(cwd: {cwd}). You help with software engineering tasks by using tools.

Rules:
- Use tools to act; never pretend to have run something.
- Call ONE tool at a time and wait for its result.
- Before editing a file, read it first with read_file.
- Prefer edit_file for small changes; write_file only for new or fully rewritten files.
- If a tool returns an error, fix your arguments and retry (max 3 times).
- If the user denies an action, ask what to do instead via ask_user or plain text.
- Keep working until the task is done, then reply with a short summary.
- Reply in the user's language (Japanese if the user writes Japanese).\
"""

INSTRUCTION_FILES = ("LCA.md", "CLAUDE.md")


def load_instructions(cwd: Path, budget_tokens: int) -> tuple[str, bool]:
    """グローバル + プロジェクトの指示ファイルを連結して返す。(text, truncated)"""
    chunks = []
    for directory in (GLOBAL_DIR, cwd):
        for name in INSTRUCTION_FILES:
            path = directory / name
            if path.is_file():
                chunks.append(f"## Instructions from {path}\n{path.read_text(encoding='utf-8')}")
                break  # LCA.md があれば CLAUDE.md は読まない
    text = "\n\n".join(chunks)
    truncated = False
    while text and estimate_tokens(text) > budget_tokens:
        text = text[: int(len(text) * 0.9)]
        truncated = True
    if truncated:
        text += "\n[... instructions truncated to fit context]"
    return text, truncated


def build_system_prompt(config: Config, skills: dict[str, Skill], cwd: Path | None = None) -> str:
    cwd = cwd or Path.cwd()
    sections = [BASE_PROMPT.format(cwd=cwd)]
    skill_section = skills_prompt_section(skills)
    if skill_section:
        sections.append(skill_section)
    instructions, truncated = load_instructions(cwd, config.instruction_budget)
    if truncated:
        print("warning: 指示ファイルが長すぎるため切り詰めました")
    if instructions:
        sections.append(instructions)
    return "\n\n".join(sections)
