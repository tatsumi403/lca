from __future__ import annotations

from . import Tool


def make_tool(console) -> Tool:
    def execute(question: str) -> str:
        console.print(f"\n[bold cyan]質問:[/bold cyan] {question}")
        try:
            answer = console.input("[bold cyan]> [/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            return "(user did not answer)"
        return answer or "(empty answer)"

    return Tool(
        name="ask_user",
        description="Ask the user a question when you need clarification or a decision. Returns their answer.",
        parameters={
            "properties": {
                "question": {"type": "string", "description": "The question to ask, in the user's language."},
            },
            "required": ["question"],
        },
        execute=execute,
    )
