"""Keyboard input handling for interactive controls."""

from enum import Enum, auto
from typing import Callable

from pynput import keyboard


class KeyAction(Enum):
    """Available keyboard actions."""

    PAUSE = auto()
    CONTINUE = auto()
    MANUAL = auto()


class KeyboardController:
    """
    Listens for keyboard input in a background thread.

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
        self._listener: keyboard.Listener | None = None
        self._running = False

    def start(self) -> None:
        """Start listening for keyboard input."""
        self._running = True
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.start()

    def stop(self) -> None:
        """Stop listening for keyboard input."""
        self._running = False
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Handle key press events."""
        if not self._running or key is None:
            return

        # Only KeyCode has char attribute, Key (special keys) does not
        if not isinstance(key, keyboard.KeyCode):
            return

        char = key.char
        if char is None:
            return

        char = char.lower()
        if char == "p":
            self._on_action(KeyAction.PAUSE)
        elif char == "c":
            self._on_action(KeyAction.CONTINUE)
        elif char == "m":
            self._on_action(KeyAction.MANUAL)
