"""
Tactics and Resources Planner
==============================
Planning-layer module that sits between Incident Objectives and Operations Tasks.

Layer hierarchy:
    Incident Objectives   — what must be accomplished
    Work Assignments      — how objectives will be planned and resourced  ← this module
    Operations Tasks      — specific executable actions for teams
    Task Detail Window    — field execution and accountability

Open the main window with:
    from modules.planning.tactics_resources import open_tactics_resources_planner
    open_tactics_resources_planner()
"""
from __future__ import annotations

from modules.planning.tactics_resources.launcher import open_tactics_resources_planner

__all__ = ["open_tactics_resources_planner"]
