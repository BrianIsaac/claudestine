"""Keyboard input handling for interactive controls.

Uses blessed for terminal-focused input (only captures when terminal has focus),
replacing the previous pynput implementation which captured globally.
"""

import threading
from enum import Enum, auto
from typing import Callable

from blessed import Terminal


class KeyAction(Enum):
    """Available keyboard actions."""

    PAUSE = auto()
    CONTINUE = auto()
    MANUAL = auto()


class KeyboardController:
    """
    Listens for keyboard input from the terminal.

    Unlike pynput which captures globally, this only captures keypresses
    when the terminal window has focus, preventing accidental triggers
    from other applications.

    Controls:
        P - Pause execution
        C - Continue execution
        M - Manual override mode
    """

    def __init__(self, on_action: Callable[[KeyAction], None]):
        """
        Initialise the keyboard controller.

        Args:
            on_action: Callback when a control key is pressed.
        """
        self._on_action = on_action
        self._terminal = Terminal()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start listening for keyboard input in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop listening for keyboard input."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
            self._thread = None

    def _listen_loop(self) -> None:
        """Background thread loop that listens for keypresses."""
        with self._terminal.cbreak():
            while self._running:
                # Non-blocking read with 100ms timeout
                key = self._terminal.inkey(timeout=0.1)

                if not key:
                    continue

                # Get the character (lowercase for comparison)
                char = str(key).lower() if key else None

                if char == "p":
                    self._on_action(KeyAction.PAUSE)
                elif char == "c":
                    self._on_action(KeyAction.CONTINUE)
                elif char == "m":
                    self._on_action(KeyAction.MANUAL)
