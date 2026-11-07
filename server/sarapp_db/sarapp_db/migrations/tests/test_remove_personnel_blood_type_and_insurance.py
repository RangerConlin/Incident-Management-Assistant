from __future__ import annotations

from sarapp_db.migrations.remove_personnel_blood_type_and_insurance import (
    IncidentPersonnelRepository,
    PersonnelRepository,
    _clean_repository,
)
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db


def test_cleanup_removes_retired_emergency_fields() -> None:
    master = PersonnelRepository(get_master_db())
    incident = IncidentPersonnelRepository(get_incident_db("TEST_RETIRED_PERSONNEL_FIELDS"))
    master_id = "test-retired-emergency-master"
    incident_id = "test-retired-emergency-incident"
    master.delete_many({"_id": master_id})
    incident.delete_many({"_id": incident_id})
    try:
        master.insert_one(
            {
                "_id": master_id,
                "name": "Test Person",
                "emergency_info": {
                    "primary_name": "Contact",
                    "blood_type": "O+",
                    "insurance": "Retired value",
                },
            }
        )
        incident.insert_one(
            {
                "_id": incident_id,
                "name": "Test Person",
                "emergency_info": {"blood_type": "A-", "insurance": "Old"},
            }
        )

        assert _clean_repository(master, dry_run=False) == 1
        assert _clean_repository(incident, dry_run=False) == 1
        master_doc = master.find_by_id(master_id, include_deleted=True)
        incident_doc = incident.find_by_id(incident_id, include_deleted=True)
        assert master_doc["emergency_info"] == {"primary_name": "Contact"}
        assert incident_doc["emergency_info"] == {}
    finally:
        master.delete_many({"_id": master_id})
        incident.delete_many({"_id": incident_id})
