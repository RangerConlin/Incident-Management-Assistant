from sarapp_db.api.routers import operations


def test_task_assets_reuses_one_team_lookup(monkeypatch):
    teams = [{"int_id": 3}]
    lookups: list[tuple[str, int]] = []

    def _teams(incident_id: str, task_id: int):
        lookups.append((incident_id, task_id))
        return teams

    monkeypatch.setattr(operations, "_task_team_docs", _teams)
    monkeypatch.setattr(operations, "_task_vehicle_rows", lambda value: [{"teams": value}])
    monkeypatch.setattr(operations, "_task_aircraft_rows", lambda value: [{"teams": value}])

    result = operations.list_task_assets("TEST-ASSETS", 9)

    assert lookups == [("TEST-ASSETS", 9)]
    assert result == {
        "vehicles": [{"teams": teams}],
        "aircraft": [{"teams": teams}],
    }


def test_task_asset_rollups_batch_master_queries(monkeypatch):
    queries: dict[str, list[dict]] = {"vehicles": [], "aircraft": []}

    class _Collection:
        def __init__(self, name: str, rows: list[dict]):
            self.name = name
            self.rows = rows

        def find(self, query):
            queries[self.name].append(query)
            return self.rows

    class _MasterDb:
        def __getitem__(self, name):
            if name == "vehicles":
                return _Collection("vehicles", [{"int_id": 4, "vehicle_id": "V-4"}])
            return _Collection("aircraft", [{"int_id": 7, "callsign": "EAGLE"}])

    monkeypatch.setattr(operations, "get_master_db", lambda: _MasterDb())
    teams = [{"vehicle_ids": [4], "aircraft_ids": [7]}]

    vehicles = operations._task_vehicle_rows(teams)
    aircraft = operations._task_aircraft_rows(teams)

    assert len(queries["vehicles"]) == 1
    assert len(queries["aircraft"]) == 1
    assert vehicles[0]["id"] == "V-4"
    assert aircraft[0]["callsign"] == "EAGLE"
