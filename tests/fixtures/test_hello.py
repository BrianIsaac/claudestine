"""Tests for the hello module."""

import pytest

from tests.fixtures.hello import greet


class TestGreet:
    """Tests for the greet function."""

    def test_greet_world(self) -> None:
        """Test greeting with 'World'."""
        result = greet("World")
        assert result == "Hello, World!"

    def test_greet_claude(self) -> None:
        """Test greeting with 'Claude'."""
        result = greet("Claude")
        assert result == "Hello, Claude!"
