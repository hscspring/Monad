"""
MONAD Tool: Ask User
Prompts the user for additional information when parameters are missing.
"""


def run(question: str = "", **kwargs) -> str:
    """Ask the user a question and return their response."""
    if not question:
        question = "Could you provide more details?"

    print(f"\n[MONAD] 🤔 {question}")
    response = input("[You] > ")
    return response.strip()


TOOL_META = {
    "name": "ask_user",
    "description": "Ask the user for clarification or additional information.",
    "inputs": ["question"],
}
