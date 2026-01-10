"""Hello module with greeting functionality."""


def greet(name: str) -> str:
    """Return a greeting message for the given name.

    Args:
        name: The name to greet.

    Returns:
        A greeting string in the format "Hello, {name}!".
    """
    return f"Hello, {name}!"
