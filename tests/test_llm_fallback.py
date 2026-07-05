from lca.llm import parse_textual_tool_call


def test_plain_json_tool_call():
    tc = parse_textual_tool_call('{"name": "bash", "arguments": {"command": "ls"}}')
    assert tc and tc.name == "bash" and tc.arguments == {"command": "ls"}


def test_alternate_keys():
    tc = parse_textual_tool_call('{"tool": "read_file", "parameters": {"path": "a.py"}}')
    assert tc and tc.name == "read_file"


def test_code_fenced_json():
    tc = parse_textual_tool_call('```json\n{"name": "bash", "arguments": {"command": "pwd"}}\n```')
    assert tc and tc.arguments == {"command": "pwd"}


def test_normal_text_is_not_tool_call():
    assert parse_textual_tool_call("これはただの返答です") is None
    assert parse_textual_tool_call('{"answer": 42}') is None
