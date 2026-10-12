"""ToolController: enforces a single active map tool at a time.

Pure logic, no Qt dependency, so it is trivially unit-testable. The map
canvas and ribbon Navigation/Draw groups both drive tool selection through
this controller so "select tool X" always deactivates whatever was active
before, and Escape always resets to the default tool.
"""

from __future__ import annotations

from typing import Callable

DEFAULT_TOOL = "pan"


class ToolController:
    """Tracks the single currently-active map tool and notifies listeners."""

    def __init__(self, default_tool: str = DEFAULT_TOOL) -> None:
        self._default_tool = default_tool
        self._active_tool = default_tool
        self._listeners: list[Callable[[str, str], None]] = []

    @property
    def active_tool(self) -> str:
        return self._active_tool

    @property
    def default_tool(self) -> str:
        return self._default_tool

    def subscribe(self, listener: Callable[[str, str], None]) -> None:
        """listener(new_tool, previous_tool) is called on every tool change."""
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[str, str], None]) -> None:
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def activate(self, tool: str) -> str:
        """Activate `tool`, deactivating whatever was active. Returns the new active tool."""
        if not tool:
            tool = self._default_tool
        previous = self._active_tool
        if tool == previous:
            return previous
        self._active_tool = tool
        for listener in list(self._listeners):
            listener(tool, previous)
        return tool

    def reset(self) -> str:
        """Reset to the default tool (used on Escape)."""
        return self.activate(self._default_tool)

    def is_active(self, tool: str) -> bool:
        return self._active_tool == tool
