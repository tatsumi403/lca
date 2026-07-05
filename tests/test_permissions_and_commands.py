from pathlib import Path

from rich.console import Console

from lca import commands
from lca.config import Config
from lca.permissions import Permissions
from lca.skills import Skill


def make_permissions(inputs: list[str]) -> Permissions:
    perms = Permissions(Config(), Console(file=open("/dev/null", "w")))
    perms._prompt = lambda options: inputs.pop(0)
    return perms


def test_bash_allowlist_auto_approves():
    perms = make_permissions([])
    assert perms.approve_bash("git status")
    assert perms.approve_bash("ls -la /tmp")


def test_bash_denylist_rejects_without_prompt():
    perms = make_permissions([])
    assert not perms.approve_bash("sudo rm -rf /etc")


def test_bash_prompt_yes_no_always():
    perms = make_permissions(["n", "y", "a"])
    assert not perms.approve_bash("npm install")
    assert perms.approve_bash("npm install")
    assert perms.approve_bash("npm run build")     # "a" → session allow
    assert perms.approve_bash("npm run test")      # 以降は自動許可 (prefix: "npm run")


def test_dispatch_builtin_and_skill(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\nname: rev\ndescription: d\n---\nレビュー手順に従う")
    skills = {"rev": Skill(name="rev", description="d", path=skill_md)}

    d = commands.dispatch("/help", skills, {})
    assert d.kind == "builtin" and d.action == "help"

    d = commands.dispatch("/rev 123", skills, {})
    assert d.kind == "prompt"
    assert "レビュー手順に従う" in d.prompt and "引数: 123" in d.prompt

    d = commands.dispatch("/nope", skills, {})
    assert d.kind == "unknown"

    d = commands.dispatch("ふつうの入力", skills, {})
    assert d.kind == "not_command"


def test_dispatch_custom_command(tmp_path: Path):
    cmd = tmp_path / "search.md"
    cmd.write_text("次のキーワードを検索: $ARGUMENTS")
    d = commands.dispatch("/search rust async", {}, {"search": cmd})
    assert d.kind == "prompt"
    assert d.prompt == "次のキーワードを検索: rust async"
