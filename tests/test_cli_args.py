from lca.cli import _parse_args, _resolve_oneshot


def test_parse_dir_and_prompt():
    args = _parse_args(["-C", "/tmp/foo", "-p", "hello world"])
    assert args.dir == "/tmp/foo"
    assert args.prompt == "hello world"
    assert args.prompt_args == []


def test_parse_positional_prompt():
    args = _parse_args(["ディレクトリ", "構成", "を教えて"])
    assert args.dir is None
    assert args.prompt is None
    assert args.prompt_args == ["ディレクトリ", "構成", "を教えて"]


def test_parse_no_args_is_repl():
    args = _parse_args([])
    assert _resolve_oneshot(args.prompt, args.prompt_args) is None


def test_resolve_oneshot_prefers_prompt_flag():
    assert _resolve_oneshot("/analyze x.log", ["ignored"]) == "/analyze x.log"


def test_resolve_oneshot_joins_positional():
    assert _resolve_oneshot(None, ["a", "b", "c"]) == "a b c"


def test_resolve_oneshot_empty_is_none():
    assert _resolve_oneshot("", []) is None
    assert _resolve_oneshot(None, []) is None
    assert _resolve_oneshot(None, ["   "]) is None
