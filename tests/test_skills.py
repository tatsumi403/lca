from pathlib import Path

from lca import skills as skills_mod
from lca.skills import Skill, load_skills, parse_frontmatter, skills_prompt_section


def make_skill(base: Path, name: str, description: str, body: str = "手順...") -> Path:
    d = base / name
    d.mkdir(parents=True)
    p = d / "SKILL.md"
    p.write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n")
    return p


def test_parse_frontmatter():
    meta = parse_frontmatter("---\nname: x\ndescription: y\n---\nbody")
    assert meta == {"name": "x", "description": "y"}
    assert parse_frontmatter("no frontmatter") is None
    assert parse_frontmatter("---\n: : broken [\n---\nbody") is None


def test_load_skills_project_overrides_global(tmp_path, monkeypatch):
    global_dir = tmp_path / "home" / ".lca"
    project = tmp_path / "proj"
    make_skill(global_dir / "skills", "review", "グローバル版")
    make_skill(global_dir / "skills", "deploy", "デプロイ手順")
    make_skill(project / ".lca" / "skills", "review", "プロジェクト版")
    monkeypatch.setattr(skills_mod, "GLOBAL_DIR", global_dir)

    result = load_skills(project)
    assert set(result) == {"review", "deploy"}
    assert result["review"].description == "プロジェクト版"


def test_skill_body_strips_frontmatter(tmp_path):
    p = make_skill(tmp_path, "s", "d", body="# 手順\n1. やる")
    skill = Skill(name="s", description="d", path=p)
    assert skill.body() == "# 手順\n1. やる"


def test_broken_frontmatter_skipped(tmp_path, monkeypatch, capsys):
    global_dir = tmp_path / ".lca"
    d = global_dir / "skills" / "broken"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\ndescription: nameがない\n---\nbody")
    monkeypatch.setattr(skills_mod, "GLOBAL_DIR", global_dir)
    assert load_skills(tmp_path) == {}
    assert "warning" in capsys.readouterr().out


def test_prompt_section_truncates_description(tmp_path):
    p = make_skill(tmp_path, "long", "あ" * 300)
    skill = Skill(name="long", description="あ" * 120 + "…", path=p)
    section = skills_prompt_section({"long": skill})
    assert "read_file" in section
    assert str(p) in section
