"""設定ファイル (config.toml) の読み込み。

~/.lca/config.toml をベースに ./.lca/config.toml で浅くマージ上書きする。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

GLOBAL_DIR = Path.home() / ".lca"
PROJECT_DIR_NAME = ".lca"

DEFAULT_BASH_ALLOWLIST = [
    "git status", "git diff", "git log", "git branch",
    "ls", "grep", "rg", "find", "cat", "head", "tail", "wc", "pwd", "which",
]
DEFAULT_BASH_DENYLIST = [
    r"\bsudo\b",
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+/(\s|$)",
    r">\s*/dev/sd",
    r"\bmkfs\b",
    r"\bshutdown\b|\breboot\b",
]


@dataclass
class Config:
    model: str = "qwen3:14b"
    ollama_host: str = "http://localhost:11434"
    num_ctx: int = 16384
    max_steps: int = 30
    tool_output_limit: int = 8000
    bash_allowlist: list[str] = field(default_factory=lambda: list(DEFAULT_BASH_ALLOWLIST))
    bash_denylist: list[str] = field(default_factory=lambda: list(DEFAULT_BASH_DENYLIST))

    @property
    def instruction_budget(self) -> int:
        # 指示ファイル+スキル一覧に許すトークン予算 (num_ctxの15%)
        return int(self.num_ctx * 0.15)


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as e:
        print(f"warning: {path} の読み込みに失敗しました: {e}")
        return {}


def load_config(cwd: Path | None = None) -> Config:
    cwd = cwd or Path.cwd()
    cfg = Config()
    for path in (GLOBAL_DIR / "config.toml", cwd / PROJECT_DIR_NAME / "config.toml"):
        data = _read_toml(path)
        perms = data.pop("permissions", {})
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        if "bash_allowlist" in perms:
            cfg.bash_allowlist = list(perms["bash_allowlist"])
        if "bash_denylist" in perms:
            cfg.bash_denylist = list(perms["bash_denylist"])
    return cfg


def save_allowlist_entry(prefix: str) -> None:
    """`A` (always) 選択時にグローバル config.toml の allowlist へ追記する。"""
    GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
    path = GLOBAL_DIR / "config.toml"
    data = _read_toml(path)
    perms = data.get("permissions", {})
    allow = perms.get("bash_allowlist", list(DEFAULT_BASH_ALLOWLIST))
    if prefix in allow:
        return
    allow.append(prefix)
    # tomllib は書き込み不可のため、素朴に再構成する（permissionsのみ管理対象）
    lines = []
    for key, value in data.items():
        if key == "permissions" or isinstance(value, dict):
            continue
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        else:
            lines.append(f"{key} = {value}")
    lines.append("")
    lines.append("[permissions]")
    lines.append("bash_allowlist = [")
    for item in allow:
        lines.append(f'    "{item}",')
    lines.append("]")
    deny = perms.get("bash_denylist")
    if deny:
        lines.append("bash_denylist = [")
        for item in deny:
            lines.append(f"    '{item}',")
        lines.append("]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
