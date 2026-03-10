"""
MONAD Tool: Ask User
Prompts the user for additional information when parameters are missing.
"""


from monad.interface.output import Output

custom_input_handler = None

def run(question: str = "", **kwargs) -> str:
    """Ask the user a question and return their response."""
    if not question:
        question = "Could you provide more details?"

    Output.system(f"🤔 [MONAD Asks]: {question}")
    # Emit a special marker so the web frontend can display the question in the chat panel
    Output._emit(f"[__WS_ASK_USER__]{question}[__WS_ASK_USER_END__]")
    
    if custom_input_handler:
        return custom_input_handler().strip()
        
    response = input("\n[You] > ")
    return response.strip()


TOOL_META = {
    "name": "ask_user",
    "description": "Ask the user for clarification or additional information.",
    "inputs": ["question"],
}
