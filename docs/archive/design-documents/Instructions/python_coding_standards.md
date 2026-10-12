# Python Coding Standards

- Follow PEP 8 and use type hints.
- Prefer dataclasses, logging, and repository/service boundaries.
- Normalize data before persistence.
- Bridge methods intended for Qt binding should use `@Slot` and emit change signals when bound state changes.
- Extend CLI quick actions in `ui/actions/quick_entry_actions.py` and add pytest coverage for new quick-action behavior.
