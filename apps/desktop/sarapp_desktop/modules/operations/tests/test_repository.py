from __future__ import annotations

from modules.operations.data import repository


class _FakeEntryCreate:
    def __init__(self, **values) -> None:
        self.__dict__.update(values)


def test_ics214_auto_entry_normalizes_integer_actor_user_id_to_string() -> None:
    recorded: dict[str, object] = {}

    class FakeIcs:
        @staticmethod
        def create_entry(inc: str, entry: _FakeEntryCreate) -> None:
            recorded["inc"] = inc
            recorded["entry"] = entry

    repository._ics214_auto_entry(
        "INC-1",
        category="team",
        ref_id=7,
        text="Team status changed to Assigned",
        ics=FakeIcs,
        EntryCreate=_FakeEntryCreate,
        actor_user_id=186,
    )

    assert recorded["inc"] == "INC-1"
    entry = recorded["entry"]
    assert isinstance(entry, _FakeEntryCreate)
    assert entry.created_by == "186"
    assert entry.team_ids == [7]
    assert entry.expand_team_members is True

