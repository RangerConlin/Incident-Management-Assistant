import os
import shutil
from pathlib import Path

from modules.personnel.services import cert_seeder
from modules.personnel.api import cert_api
from utils.db import get_master_conn


def _setup_tmp_data(tmp_path: Path):
    os.environ["CHECKIN_DATA_DIR"] = str(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)


def test_profile_lsar_team_leader(tmp_path):
    _setup_tmp_data(tmp_path)
    changed, msg = cert_seeder.sync()
    assert "catalog" in msg.lower()

    # Find cert ids for GTL and SARTECH-1
    cats = cert_api.list_catalog()
    code_to_id = {c["code"]: c["id"] for c in cats}
    gtl_id = code_to_id.get("GTL")
    s1_id = code_to_id.get("SARTECH-1")
    assert gtl_id or s1_id

    person_id = 101

    # Case 1: GTL level 2 qualifies
    if gtl_id:
        cert_api.set_personnel_cert(person_id, gtl_id, 2, None)
        assert cert_api.person_meets_profile(person_id, "LSAR_TEAM_LEADER") is True
        cert_api.set_personnel_cert(person_id, gtl_id, 1, None)
        assert cert_api.person_meets_profile(person_id, "LSAR_TEAM_LEADER") is False

    # Case 2: SARTECH-1 level 2 qualifies
    if s1_id:
        cert_api.set_personnel_cert(person_id, s1_id, 2, None)
        assert cert_api.person_meets_profile(person_id, "LSAR_TEAM_LEADER") is True
        cert_api.set_personnel_cert(person_id, s1_id, 1, None)
        assert cert_api.person_meets_profile(person_id, "LSAR_TEAM_LEADER") is False

