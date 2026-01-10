"""Tests for the hello module."""

from hello import greet


def test_greet_world() -> None:
    """Test that greet returns correct greeting for World."""
    result = greet("World")
    assert result == "Hello, World!"


def test_greet_claude() -> None:
    """Test that greet returns correct greeting for Claude."""
    result = greet("Claude")
    assert result == "Hello, Claude!"
