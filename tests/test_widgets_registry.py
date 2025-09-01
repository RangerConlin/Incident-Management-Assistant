from ui.widgets import registry as W


def test_registry_contains_all_ids():
    expected = {
        # Incident Context
        "incidentinfo",
        # Status & Operations
        "teamstatusboard", "taskstatusboard", "personnelavailablility", "equipmentsnapshot", "vehairsnapshot", "opsDashboardFeed",
        # Communications
        "recentmessages", "notifications", "ics205commplan", "commlogfeed",
        # Planning & Documentation
        "objectivestracker", "formsinprogress", "sitrepfeed", "upcomingtasks",
        # Medical & Safety
        "safetyalerts", "medicalincidentlog", "ics206snapshot",
        # Intel & Mapping
        "inteldashboard", "cluelogsnapshot", "mapsnapshot",
        # Public Information
        "pressDrafts", "mediaLog", "briefingqueue",
        # Quick Entry & Time
        "quickEntry", "quickEntryCLI", "clockDual",
    }
    assert expected.issubset(W.REGISTRY.keys())


def test_spec_shapes_minimal():
    for wid, spec in W.REGISTRY.items():
        assert spec.id == wid
        assert spec.title and isinstance(spec.title, str)
        assert spec.default_size.w >= spec.min_size.w
        assert spec.default_size.h >= spec.min_size.h

