"""
Section layout presets for the Window → Section Layouts menu.

Each entry maps a section_id to a label and an ordered list of
(widget_id, area_key) pairs.  area_key is one of:
  "center", "left", "right", "bottom", "top"

To add a new layout: add a new key here. main.py reads this file at
startup and builds the submenu automatically — no other changes needed.
"""

SECTION_LAYOUTS = {
    "ic": {
        "label": "Incident Command",
        "widgets": [
            ("incidentinfo",      "center"),
            ("opperiod",          "left"),
            ("weather",           "left"),
            ("teamstatusboard",   "right"),
            ("objectivestracker", "bottom"),
            ("safetyalerts",      "bottom"),
            ("clockDual",         "right"),
        ],
    },
    "operations": {
        "label": "Operations",
        "widgets": [
            ("teamstatusboard", "center"),
            ("taskstatusboard", "center"),
            ("upcomingtasks",   "right"),
            ("activitylog",     "bottom"),
            ("commlogfeed",     "bottom"),
        ],
    },
    "logistics": {
        "label": "Logistics",
        "widgets": [
            ("resourcerequests",      "center"),
            ("personnelavailability", "left"),
            ("equipmentsnapshot",     "left"),
            ("vehairsnapshot",        "left"),
            ("commlogfeed",           "bottom"),
        ],
    },
    "planning": {
        "label": "Planning",
        "widgets": [
            ("objectivestracker", "center"),
            ("opperiod",          "left"),
            ("activitylog",       "center"),
            ("upcomingtasks",     "right"),
            ("formsinprogress",   "right"),
        ],
    },
    "safety": {
        "label": "Safety",
        "widgets": [
            ("safetyalerts",    "center"),
            ("weather",         "left"),
            ("teamstatusboard", "right"),
            ("notifications",   "bottom"),
        ],
    },
    "medical": {
        "label": "Medical",
        "widgets": [
            ("medicalincidentlog", "center"),
            ("ics206snapshot",     "left"),
            ("safetyalerts",       "right"),
        ],
    },
    "pio": {
        "label": "Public Information",
        "widgets": [
            ("subjectprofile", "center"),
            ("pressDrafts",    "center"),
            ("briefingqueue",  "right"),
            ("mediaLog",       "right"),
            ("notifications",  "bottom"),
        ],
    },
    "comms": {
        "label": "Communications",
        "widgets": [
            ("ics205commplan", "center"),
            ("commlogfeed",    "center"),
            ("recentmessages", "right"),
            ("notifications",  "bottom"),
        ],
    },
}
