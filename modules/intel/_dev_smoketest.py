"""Quick smoke test for the intel module.

The script seeds a small set of data in a temporary incident database and
verifies that basic CRUD operations execute without errors.  It is not a
replacement for a full test suite but provides a convenient way to ensure the
module wires together correctly when run in isolation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from utils import incident_context

from .utils import db_access
from .models import Clue, Subject, EnvSnapshot, IntelReport, FormEntry


def main() -> None:
    incident_context.set_active_incident("devtest")
    db_access.ensure_incident_schema()
    with db_access.incident_session() as session:
        # Seed subjects
        for i in range(5):
            session.add(Subject(name=f"Subject {i}", sex="U"))
        # Seed clues
        now = datetime.utcnow()
        for i in range(10):
            session.add(
                Clue(
                    type="observation",
                    score=i,
                    at_time=now + timedelta(minutes=i),
                    location_text=f"Zone {i}",
                    entered_by="tester",
                )
            )
        # Seed environment snapshots
        for i in range(3):
            session.add(EnvSnapshot(op_period=i + 1, notes=f"Notes {i}"))
        # Seed reports
        for i in range(2):
            session.add(IntelReport(title=f"Report {i}", body_md="Sample body"))
        # Seed forms
        for i in range(4):
            session.add(FormEntry(form_name=f"Form {i}", data_json="{}"))
        session.commit()
    print("Smoke test data created")


if __name__ == "__main__":
    main()
