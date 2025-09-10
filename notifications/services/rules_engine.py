from __future__ import annotations

from typing import Callable, Dict, Any, List


class RulesEngine:
    """Very small rules engine placeholder."""

    def __init__(self, notifier) -> None:
        self.notifier = notifier
        self._rules: List[Callable[[Dict[str, Any]], None]] = []

    def add_rule(self, func: Callable[[Dict[str, Any]], None]) -> None:
        self._rules.append(func)

    def evaluate(self, context: Dict[str, Any]) -> None:
        for rule in list(self._rules):
            try:
                rule(context)
            except Exception:
                pass
