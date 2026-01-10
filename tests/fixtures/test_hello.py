"""Tests for the hello module."""

from tests.fixtures.hello import greet


def test_greet_world():
    """Test that greet returns correct message for World."""
    assert greet("World") == "Hello, World!"


def test_greet_claude():
    """Test that greet returns correct message for Claude."""
    assert greet("Claude") == "Hello, Claude!"
