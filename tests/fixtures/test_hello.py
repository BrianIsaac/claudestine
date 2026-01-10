"""Tests for the hello module."""

from tests.fixtures.hello import greet


def test_greet_world() -> None:
    """Test that greet returns correct greeting for World."""
    assert greet("World") == "Hello, World!"


def test_greet_claude() -> None:
    """Test that greet returns correct greeting for Claude."""
    assert greet("Claude") == "Hello, Claude!"
