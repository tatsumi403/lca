# lca — Local Coding Agent

Claude Code 風のAIコーディングエージェントCLI。**完全ローカル**（LLM含めて外部API不使用）で動作します。

- LLM: [Ollama](https://ollama.com)（デフォルト: `qwen3:14b`）
- ツールは5個のみ: `bash` / `read_file` / `write_file` / `edit_file` / `ask_user`
- スキル（SKILL.md）、カスタムスラッシュコマンド、指示ファイル（LCA.md / CLAUDE.md互換）対応

## セットアップ

```bash
# Ollama（未導入の場合）
brew install ollama
brew services start ollama
ollama pull qwen3:14b

# lca 本体
cd lca
uv sync
uv run lca            # または: uv tool install --editable . && lca
```

## 使い方

```
› このディレクトリの構成を教えて          # 自然文で指示
› /skills                                  # スキル一覧
› /code-review 123                         # スキルの明示呼び出し
› /compact                                 # 履歴をLLM要約で圧縮
› /help
```

### 一発実行 / どこからでも実行

引数を渡すと、REPL に入らず1ターンだけ実行して終了する（スクリプトや別ディレクトリからの呼び出し向け）:

```bash
lca -p "このリポジトリの構成を教えて"        # -p で指示を渡して即実行
lca このリポジトリの構成を教えて              # 位置引数でも同じ
lca -C /path/to/project -p "/code-review"    # -C で作業ディレクトリを切り替えてから実行
```

- `-C/--dir DIR`: 起動前に `DIR` へ移動（設定・スキル・指示ファイル・相対パスの読込基準になる）
- `-p/--prompt TEXT`: 指示を1ターン実行して終了。省略時は従来どおり対話 REPL

ツール実行時は承認プロンプトが出ます:
- `y` 1回許可 / `n` 拒否 / `a` セッション中許可 / `A` 設定ファイルに保存して常時許可
- 読み取り (`read_file`) と allowlist 登録済みコマンド（`git status`, `ls` 等）は自動許可

## 設定

`~/.lca/config.toml`（プロジェクト側 `./.lca/config.toml` で上書き）:

```toml
model = "qwen3:14b"
ollama_host = "http://localhost:11434"
num_ctx = 32768          # コンテキスト長。メモリと相談（16GB機なら16384）
max_steps = 30           # 1ターン内のツール実行上限
tool_output_limit = 8000 # ツール出力の切り詰め文字数

[permissions]
bash_allowlist = ["git status", "git diff", "ls", "grep", "cat"]
```

## スキル

`~/.lca/skills/<name>/SKILL.md`（グローバル）または `./.lca/skills/<name>/SKILL.md`（プロジェクト優先）:

```markdown
---
name: code-review
description: コードの変更をレビューして日本語でフィードバックする
---

# 手順
1. git diff で変更を確認する
2. バグ・可読性・パフォーマンスの観点でレビューする
...
```

- 起動時に name/description だけがシステムプロンプトに載り、タスクが合致するとモデルが本文を `read_file` して従う（progressive disclosure）
- `/code-review 引数` で明示呼び出しも可能

## カスタムコマンド

`~/.lca/commands/<name>.md` に本文を書き、`$ARGUMENTS` が引数に置換される。`/name 引数` で実行。

## 指示ファイル

`./LCA.md`（なければ `./CLAUDE.md` を互換で読む）と `~/.lca/LCA.md` がシステムプロンプトに連結される。

## 推奨モデル（Apple Silicon、ツールコール精度重視）

| メモリ | モデル | num_ctx |
|---|---|---|
| 16GB | `qwen3:8b` | 16384 |
| 32GB+ | `qwen3:14b` | 32768 |
| 64GB+ | `gpt-oss:20b` / `qwen3:32b` | 32768+ |

## 開発

```bash
uv run pytest        # ユニットテスト
```

## v1で意図的に削った機能

サブエージェント / Hooks / プラグイン / LSP / MCP / 内蔵Web検索（Bash経由で `gemini` CLI等を呼べば代替可能）/ Planモード。
MCP対応は `src/lca/tools/__init__.py` のレジストリにアダプタを足せば追加できる構造にしてある（v2候補）。
