from pathlib import Path

import pytest

from lca.config import Config
from lca.tools import files


@pytest.fixture
def tools():
    made = files.make_tools(Config())
    return {t.name: t for t in made}


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    p = tmp_path / "sample.py"
    p.write_text("def foo():\n    return 1\n\ndef bar():\n    return 1\n")
    return p


def test_edit_unique_match(tools, sample):
    result = tools["edit_file"].execute(
        path=str(sample), old_string="def foo():\n    return 1", new_string="def foo():\n    return 2")
    assert "Replaced 1" in result
    assert "return 2" in sample.read_text()


def test_edit_not_found(tools, sample):
    result = tools["edit_file"].execute(
        path=str(sample), old_string="nonexistent", new_string="x")
    assert result.startswith("Error:")
    assert "not found" in result


def test_edit_ambiguous(tools, sample):
    result = tools["edit_file"].execute(
        path=str(sample), old_string="    return 1", new_string="    return 9")
    assert result.startswith("Error:")
    assert "2 times" in result
    # replace_all で解決できる
    result = tools["edit_file"].execute(
        path=str(sample), old_string="    return 1", new_string="    return 9", replace_all=True)
    assert "Replaced 2" in result


def test_read_file_numbered(tools, sample):
    result = tools["read_file"].execute(path=str(sample))
    assert result.startswith("1\tdef foo():")


def test_read_missing(tools, tmp_path):
    result = tools["read_file"].execute(path=str(tmp_path / "nope.txt"))
    assert result.startswith("Error:")


def test_write_creates_parents(tools, tmp_path):
    target = tmp_path / "a" / "b" / "new.txt"
    result = tools["write_file"].execute(path=str(target), content="hello")
    assert "Wrote 5 chars" in result
    assert target.read_text() == "hello"


def test_arg_alias_normalization(tools):
    tool = tools["read_file"]
    assert tool.normalize_args({"file_path": "x.txt", "limit": 5}) == {"path": "x.txt", "limit": 5}


def test_validate_missing_required(tools):
    error = tools["edit_file"].validate({"path": "x"})
    assert error and "old_string" in error
