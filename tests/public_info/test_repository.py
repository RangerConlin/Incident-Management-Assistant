import sys
from pathlib import Path
import shutil

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from modules.public_info.models.repository import PublicInfoRepository

TEST_MISSION_ID = 999
DB_PATH = Path("data/missions") / f"{TEST_MISSION_ID}.db"


def setup_module(module):
    if DB_PATH.exists():
        DB_PATH.unlink()


def teardown_module(module):
    if DB_PATH.exists():
        DB_PATH.unlink()


def test_state_transitions_and_revision():
    repo = PublicInfoRepository(TEST_MISSION_ID)
    msg = repo.create_message(
        {
            "title": "Initial",
            "body": "Body",
            "type": "PressRelease",
            "audience": "Public",
            "created_by": 1,
        }
    )
    assert msg["status"] == "Draft"
    msg = repo.update_message(msg["id"], {"title": "Updated"}, 1)
    assert msg["revision"] == 2
    msg = repo.submit_for_review(msg["id"], 1)
    assert msg["status"] == "InReview"
    approver = {"id": 2, "roles": ["PIO"]}
    msg = repo.approve_message(msg["id"], approver)
    assert msg["status"] == "Approved"
    lead = {"id": 3, "roles": ["LeadPIO"]}
    msg = repo.publish_message(msg["id"], lead)
    assert msg["status"] == "Published"
    msg = repo.archive_message(msg["id"], 1)
    assert msg["status"] == "Archived"


def test_permission_checks():
    repo = PublicInfoRepository(TEST_MISSION_ID)
    msg = repo.create_message(
        {
            "title": "Test",
            "body": "Body",
            "type": "Advisory",
            "audience": "Public",
            "created_by": 1,
        }
    )
    repo.submit_for_review(msg["id"], 1)
    with pytest.raises(PermissionError):
        repo.approve_message(msg["id"], {"id": 2, "roles": []})
    approver = {"id": 2, "roles": ["PIO"]}
    repo.approve_message(msg["id"], approver)
    with pytest.raises(PermissionError):
        repo.publish_message(msg["id"], {"id": 2, "roles": ["PIO"]})
    repo.publish_message(msg["id"], {"id": 3, "roles": ["LeadPIO"]})
