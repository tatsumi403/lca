"""スキルローダー (progressive disclosure)。

~/.lca/skills/*/SKILL.md と ./.lca/skills/*/SKILL.md を探索し、
起動時は frontmatter (name/description) のみパースする。本文はモデルが
read_file で必要時に読む。/スキル名 の明示呼び出し時のみ本文を展開する。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import GLOBAL_DIR, PROJECT_DIR_NAME

DESC_LIMIT = 120


@dataclass
class Skill:
    name: str
    description: str
    path: Path

    def body(self) -> str:
        text = self.path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        return parts[2].strip() if len(parts) >= 3 and text.startswith("---") else text


def parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def load_skills(cwd: Path | None = None) -> dict[str, Skill]:
    cwd = cwd or Path.cwd()
    skills: dict[str, Skill] = {}
    # グローバル → プロジェクトの順（同名はプロジェクト優先で上書き）
    for base in (GLOBAL_DIR / "skills", cwd / PROJECT_DIR_NAME / "skills"):
        if not base.is_dir():
            continue
        for skill_md in sorted(base.glob("*/SKILL.md")):
            try:
                meta = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            except OSError:
                continue
            if not meta or "name" not in meta or "description" not in meta:
                print(f"warning: frontmatter が不正なためスキップ: {skill_md}")
                continue
            name = str(meta["name"]).strip()
            desc = " ".join(str(meta["description"]).split())
            if len(desc) > DESC_LIMIT:
                desc = desc[:DESC_LIMIT] + "…"
            skills[name] = Skill(name=name, description=desc, path=skill_md)
    return skills


def skills_prompt_section(skills: dict[str, Skill]) -> str:
    if not skills:
        return ""
    lines = [
        "# Skills",
        "The following skills are available. When a task matches a skill's "
        "description, you MUST first call read_file on its path and follow "
        "the instructions inside before proceeding.",
        "",
    ]
    for skill in skills.values():
        lines.append(f"- {skill.name}: {skill.description}")
        lines.append(f"  (path: {skill.path})")
    return "\n".join(lines)
