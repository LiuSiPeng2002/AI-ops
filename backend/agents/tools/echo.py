from langchain_core.tools import tool


@tool
def echo_tool(message: str) -> str:
    """Echo back the input message. Use this to verify the tool calling pipeline works correctly.

    Args:
        message: The message to echo back.

    Returns:
        The same message prefixed with 'Echo: '.
    """
    return f"Echo: {message}"
