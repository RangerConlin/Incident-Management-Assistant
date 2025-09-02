import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    import utils.incident_context as ic
    importlib.reload(ic)
    ic.set_active_incident("test_incident")

    # Lightweight package scaffolding to avoid heavy Qt imports
    modules_pkg = types.ModuleType("modules")
    modules_pkg.__path__ = []
    operations_pkg = types.ModuleType("modules.operations")
    operations_pkg.__path__ = []
    operations_data_pkg = types.ModuleType("modules.operations.data")
    operations_data_pkg.__path__ = [str(ROOT / "modules/operations/data")]
    operations_teams_pkg = types.ModuleType("modules.operations.teams")
    operations_teams_pkg.__path__ = [str(ROOT / "modules/operations/teams")]
    operations_teams_data_pkg = types.ModuleType("modules.operations.teams.data")
    operations_teams_data_pkg.__path__ = [str(ROOT / "modules/operations/teams/data")]
    communications_pkg = types.ModuleType("modules.communications")
    communications_pkg.__path__ = [str(ROOT / "modules/communications")]
    communications_models_pkg = types.ModuleType("modules.communications.models")
    communications_models_pkg.__path__ = [str(ROOT / "modules/communications/models")]
    sys.modules.update(
        {
            "modules": modules_pkg,
            "modules.operations": operations_pkg,
            "modules.operations.data": operations_data_pkg,
            "modules.operations.teams": operations_teams_pkg,
            "modules.operations.teams.data": operations_teams_data_pkg,
            "modules.communications": communications_pkg,
            "modules.communications.models": communications_models_pkg,
        }
    )

    # Load required modules via file specs
    spec = importlib.util.spec_from_file_location(
        "modules.operations.data.repository",
        ROOT / "modules/operations/data/repository.py",
    )
    ops_repo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = ops_repo
    spec.loader.exec_module(ops_repo)
    with ops_repo._connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS teams (id INTEGER PRIMARY KEY)")
        con.commit()

    spec = importlib.util.spec_from_file_location(
        "modules.operations.teams.data.team",
        ROOT / "modules/operations/teams/data/team.py",
    )
    team_model = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = team_model
    spec.loader.exec_module(team_model)

    spec = importlib.util.spec_from_file_location(
        "modules.operations.teams.data.repository",
        ROOT / "modules/operations/teams/data/repository.py",
    )
    team_repo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = team_repo
    spec.loader.exec_module(team_repo)

    spec = importlib.util.spec_from_file_location(
        "modules.communications.repository",
        ROOT / "modules/communications/repository.py",
    )
    comm_repo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = comm_repo
    spec.loader.exec_module(comm_repo)
    comm_repo.DATA_DIR = tmp_path

    spec = importlib.util.spec_from_file_location(
        "modules.communications.models.comms_models",
        ROOT / "modules/communications/models/comms_models.py",
    )
    comm_models = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = comm_models
    spec.loader.exec_module(comm_models)

    spec = importlib.util.spec_from_file_location(
        "modules.communications.radio_log",
        ROOT / "modules/communications/radio_log.py",
    )
    radio_log = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = radio_log
    spec.loader.exec_module(radio_log)

    return ic, team_repo, radio_log


def test_radio_log_resets_timer(setup_env):
    ic, team_repo, radio_log = setup_env
    from modules.operations.teams.data.team import Team

    team = Team(name="Alpha")
    team_repo.save_team(team)
    assert team_repo.get_team(team.team_id).last_comm_ts is None

    radio_log.log_radio_entry("test_incident", sender="Alpha", recipient="Ops", message="hi")

    updated = team_repo.get_team(team.team_id)
    assert updated.last_comm_ts is not None
