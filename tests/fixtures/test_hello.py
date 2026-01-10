"""Tests for the hello module."""

from .hello import greet


def test_greet_world() -> None:
    """Test greeting with 'World'."""
    result = greet("World")
    assert result == "Hello, World!"


def test_greet_claude() -> None:
    """Test greeting with 'Claude'."""
    result = greet("Claude")
    assert result == "Hello, Claude!"
