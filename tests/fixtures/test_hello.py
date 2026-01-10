"""Tests for the hello module."""

import pytest

from hello import greet


def test_greet_world() -> None:
    """Test greeting World."""
    assert greet("World") == "Hello, World!"


def test_greet_claude() -> None:
    """Test greeting Claude."""
    assert greet("Claude") == "Hello, Claude!"
