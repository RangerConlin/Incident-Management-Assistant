from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class NarrativeEntry:
    id: int
    timestamp: str
    entry_text: str
    entered_by: str
    team_name: Optional[str] = None
    critical_flag: bool = False


@dataclass
class TaskTeam:
    id: int
    team_id: int
    team_name: str
    team_leader: str
    team_leader_phone: str
    status: str
    sortie_number: Optional[str] = None
    assigned_ts: Optional[str] = None
    briefed_ts: Optional[str] = None
    enroute_ts: Optional[str] = None
    arrival_ts: Optional[str] = None
    discovery_ts: Optional[str] = None
    complete_ts: Optional[str] = None
    primary: bool = False


@dataclass
class Task:
    id: int
    task_id: str
    title: str
    description: str
    category: str
    task_type: Optional[str]
    priority: str
    status: str
    location: str
    created_by: str
    created_at: str
    assigned_to: Optional[str] = None
    due_time: Optional[str] = None


@dataclass
class TaskDetail:
    task: Task
    narrative: List[NarrativeEntry] = field(default_factory=list)
    teams: List[TaskTeam] = field(default_factory=list)
    # Personnel, Vehicles, Assignment, Comms, Debrief, Log, Attachments, Planning can be added as needed

