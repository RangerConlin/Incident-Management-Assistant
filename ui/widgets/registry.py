from __future__ import annotations

from typing import Dict

from .base import WidgetSpec, Size
from . import data_providers as dp
from .components import (
    IncidentInfoWidget,
    TeamStatusBoardWidget,
    TaskStatusBoardWidget,
    PersonnelAvailabilityWidget,
    EquipmentSnapshotWidget,
    VehicleSnapshotWidget,
    OpsDashboardFeedWidget,
    RecentMessagesWidget,
    NotificationsWidget,
    ICS205CommPlanWidget,
    CommLogFeedWidget,
    ObjectivesTrackerWidget,
    FormsInProgressWidget,
    SitrepFeedWidget,
    UpcomingTasksWidget,
    SafetyAlertsWidget,
    MedicalIncidentLogWidget,
    ICS206SnapshotWidget,
    IntelDashboardWidget,
    ClueLogSnapshotWidget,
    MapSnapshotWidget,
    PressDraftsWidget,
    MediaLogWidget,
    BriefingQueueWidget,
    QuickEntryWidget,
    ClockDualWidget,
)


def _wrap_list_widget(title: str, items: list[str]):
    # helper factory to avoid lambdas in registry construction
    class W(TeamStatusBoardWidget):
        def __init__(self, *a, **k):
            super().__init__(title=title, items=items)
    return W


def _team_status_items():
    s = dp.teams_getStatusSummary()
    return [f"Available: {s.get('available',0)}", f"Assigned: {s.get('assigned',0)}", f"Out of Service: {s.get('out_of_service',0)}"]


def _task_status_items():
    s = dp.tasks_getSummary_active()
    return [f"Draft: {s.get('draft',0)}", f"In-Progress: {s.get('in_progress',0)}", f"Completed: {s.get('completed',0)}"]


REGISTRY: Dict[str, WidgetSpec] = {
    # Incident Context
    "incidentinfo": WidgetSpec(
        id="incidentinfo",
        title="Incident Info",
        default_size=Size(4, 1),
        min_size=Size(3, 1),
        component=lambda: IncidentInfoWidget(dp.incident_getSummary, dp.auth_getCurrentUser),  # type: ignore
        data_hooks={"incident.getSummary": dp.incident_getSummary, "auth.getCurrentUser": dp.auth_getCurrentUser},
    ),

    # Status & Operations
    "teamstatusboard": WidgetSpec(
        id="teamstatusboard",
        title="Team Status",
        default_size=Size(4, 1),
        min_size=Size(3, 1),
        component=lambda: TeamStatusBoardWidget(title="Team Status", items=_team_status_items()),  # type: ignore
        data_hooks={"teams.getStatusSummary": dp.teams_getStatusSummary},
    ),
    "taskstatusboard": WidgetSpec(
        id="taskstatusboard",
        title="Task Status",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: TaskStatusBoardWidget(title="Task Status", items=_task_status_items()),  # type: ignore
        data_hooks={"tasks.getSummary": dp.tasks_getSummary_active},
    ),
    "personnelavailability": WidgetSpec(
        id="personnelavailability",
        title="Personnel Checked In",
        default_size=Size(4, 1),
        min_size=Size(3, 1),
        component=lambda: PersonnelAvailabilityWidget(
            title="Personnel Availability",
            items=[f"{k.title()}: {v}" for k, v in dp.personnel_getAvailabilitySummary().items()],
        ),  # type: ignore
        data_hooks={"personnel.getAvailabilitySummary": dp.personnel_getAvailabilitySummary},
    ),
    "equipmentsnapshot": WidgetSpec(
        id="equipmentsnapshot",
        title="Equipment Snapshot",
        default_size=Size(4, 1),
        min_size=Size(3, 1),
        component=lambda: EquipmentSnapshotWidget(
            title="Equipment",
            items=[f"{k.replace('_',' ').title()}: {v}" for k, v in dp.equipment_getSnapshot().items()],
        ),  # type: ignore
        data_hooks={"equipment.getSnapshot": dp.equipment_getSnapshot},
    ),
    "vehairsnapshot": WidgetSpec(
        id="vehairsnapshot",
        title="Vehicle Snapshot",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: VehicleSnapshotWidget(
            title="Vehicles/Aircraft",
            items=[*(f"{v['unit']}: {v['status']}" for v in dp.vehicles_getStatus()), *(
                f"{a['tail']}: {a['status']}" for a in dp.aircraft_getStatus()
            )],
        ),  # type: ignore
        data_hooks={"vehicles.getStatus": dp.vehicles_getStatus, "aircraft.getStatus": dp.aircraft_getStatus},
    ),
    "opsDashboardFeed": WidgetSpec(
        id="opsDashboardFeed",
        title="Operations Feed",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: OpsDashboardFeedWidget(title="Ops Events", items=dp.ops_getRecentEvents(20)),  # type: ignore
        data_hooks={"ops.getRecentEvents": dp.ops_getRecentEvents},
    ),

    # Communications
    "recentmessages": WidgetSpec(
        id="recentmessages",
        title="Recent Messages",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: RecentMessagesWidget(title="Messages", items=dp.comms_getRecentMessages(20)),  # type: ignore
        data_hooks={"comms.getRecentMessages": dp.comms_getRecentMessages},
    ),
    "notifications": WidgetSpec(
        id="notifications",
        title="Notifications",
        default_size=Size(3, 1),
        min_size=Size(3, 1),
        component=lambda: NotificationsWidget(title="Notifications", items=dp.alerts_getAll_min_info()),  # type: ignore
        data_hooks={"alerts.getAll": dp.alerts_getAll_min_info},
    ),
    "ics205commplan": WidgetSpec(
        id="ics205commplan",
        title="ICS-205",
        default_size=Size(3, 1),
        min_size=Size(3, 1),
        component=lambda: ICS205CommPlanWidget(title="Primary Channels", items=dp.comms_getPrimaryFrequencies()),  # type: ignore
        data_hooks={"comms.getPrimaryFrequencies": dp.comms_getPrimaryFrequencies},
    ),
    "commlogfeed": WidgetSpec(
        id="commlogfeed",
        title="Comms Log",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: CommLogFeedWidget(title="Comms Log", items=dp.comms_getCommsLog(50)),  # type: ignore
        data_hooks={"comms.getCommsLog": dp.comms_getCommsLog},
    ),

    # Planning & Documentation
    "objectivestracker": WidgetSpec(
        id="objectivestracker",
        title="Objectives",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: ObjectivesTrackerWidget(title="Incident Objectives", items=dp.planning_getObjectives()),  # type: ignore
        data_hooks={"planning.getObjectives": dp.planning_getObjectives},
    ),
    "formsinprogress": WidgetSpec(
        id="formsinprogress",
        title="Open Forms",
        default_size=Size(4, 1),
        min_size=Size(3, 1),
        component=lambda: FormsInProgressWidget(title="Forms In Progress", items=["ICS-214", "ICS-213"]),  # type: ignore
        data_hooks={"forms.getInProgress": lambda: ["ICS-214", "ICS-213"]},
    ),
    "sitrepfeed": WidgetSpec(
        id="sitrepfeed",
        title="SITREP",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: SitrepFeedWidget(title="SITREP", items=dp.planning_getSITREP(25)),  # type: ignore
        data_hooks={"planning.getSITREP": dp.planning_getSITREP},
    ),
    "upcomingtasks": WidgetSpec(
        id="upcomingtasks",
        title="Upcoming Tasks",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: UpcomingTasksWidget(title="Upcoming", items=dp.planning_getUpcomingTasks()),  # type: ignore
        data_hooks={"planning.getUpcomingTasks": dp.planning_getUpcomingTasks},
    ),

    # Medical & Safety
    "safetyalerts": WidgetSpec(
        id="safetyalerts",
        title="Safety Alerts",
        default_size=Size(3, 1),
        min_size=Size(3, 1),
        component=lambda: SafetyAlertsWidget(title="Safety Alerts", items=dp.safety_getAlerts()),  # type: ignore
        data_hooks={"safety.getAlerts": dp.safety_getAlerts},
    ),
    "medicalincidentlog": WidgetSpec(
        id="medicalincidentlog",
        title="Medical Incidents",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: MedicalIncidentLogWidget(title="Medical", items=dp.medical_getIncidentLog(25)),  # type: ignore
        data_hooks={"medical.getIncidentLog": dp.medical_getIncidentLog},
    ),
    "ics206snapshot": WidgetSpec(
        id="ics206snapshot",
        title="ICS-206 Snapshot",
        default_size=Size(4, 1),
        min_size=Size(3, 1),
        component=lambda: ICS206SnapshotWidget(title="ICS-206", items=[
            f"Hospitals: {dp.medical_get206Summary().get('hospitals',0)}",
            f"Medevac: {dp.medical_get206Summary().get('medevac','-')}",
        ]),  # type: ignore
        data_hooks={"medical.get206Summary": dp.medical_get206Summary},
    ),

    # Intel & Mapping
    "inteldashboard": WidgetSpec(
        id="inteldashboard",
        title="Intel Dashboard",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: IntelDashboardWidget(title="Intel", items=[
            f"Clues: {dp.intel_getDashboard().get('clues',0)}",
            f"Interviews: {dp.intel_getDashboard().get('interviews',0)}",
        ]),  # type: ignore
        data_hooks={"intel.getDashboard": dp.intel_getDashboard},
    ),
    "cluelogsnapshot": WidgetSpec(
        id="cluelogsnapshot",
        title="Clue Log",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: ClueLogSnapshotWidget(title="Clue Log", items=dp.intel_getClueLog(25)),  # type: ignore
        data_hooks={"intel.getClueLog": dp.intel_getClueLog},
    ),
    "mapsnapshot": WidgetSpec(
        id="mapsnapshot",
        title="Map Snapshot",
        default_size=Size(12, 2),
        min_size=Size(6, 1),
        component=lambda: MapSnapshotWidget(title="Map Snapshot", items=[str(dp.gis_getSnapshot())]),  # type: ignore
        data_hooks={"gis.getSnapshot": dp.gis_getSnapshot},
    ),

    # Public Information
    "pressDrafts": WidgetSpec(
        id="pressDrafts",
        title="Draft Press Releases",
        default_size=Size(6, 1),
        min_size=Size(4, 1),
        component=lambda: PressDraftsWidget(title="Press Drafts", items=dp.pio_getPressDrafts()),  # type: ignore
        data_hooks={"pio.getPressDrafts": dp.pio_getPressDrafts},
    ),
    "mediaLog": WidgetSpec(
        id="mediaLog",
        title="Media Log",
        default_size=Size(4, 1),
        min_size=Size(3, 1),
        component=lambda: MediaLogWidget(title="Media Log", items=dp.pio_getMediaLog(25)),  # type: ignore
        data_hooks={"pio.getMediaLog": dp.pio_getMediaLog},
    ),
    "briefingqueue": WidgetSpec(
        id="briefingqueue",
        title="Briefing Queue",
        default_size=Size(4, 1),
        min_size=Size(3, 1),
        component=lambda: BriefingQueueWidget(title="Briefing Queue", items=dp.pio_getPendingApprovals()),  # type: ignore
        data_hooks={"pio.getPendingApprovals": dp.pio_getPendingApprovals},
    ),

    # Quick Entry & Timekeeping
    "quickEntry": WidgetSpec(
        id="quickEntry",
        title="Quick Entry",
        default_size=Size(6, 1),
        min_size=Size(6, 1),
        component=None,  # constructed in dashboard with action router
        data_hooks=None,
    ),
    "quickEntryCLI": WidgetSpec(
        id="quickEntryCLI",
        title="Quick Entry CLI",
        default_size=Size(6, 1),
        min_size=Size(6, 1),
        component=None,  # included inside Quick Entry widget
        data_hooks=None,
    ),
    "clockDual": WidgetSpec(
        id="clockDual",
        title="Clock (Local+UTC)",
        default_size=Size(3, 1),
        min_size=Size(3, 1),
        component=ClockDualWidget,  # type: ignore
        data_hooks={"settings.getTimezone": lambda: None},
    ),
}

