"""Tests for the hello module."""

from hello import greet


def test_greet_world():
    """Test greeting with 'World'."""
    assert greet("World") == "Hello, World!"


def test_greet_claude():
    """Test greeting with 'Claude'."""
    assert greet("Claude") == "Hello, Claude!"
