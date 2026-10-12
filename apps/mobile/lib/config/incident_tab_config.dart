import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/incident_category.dart';
import '../screens/schedule_screen.dart';
import '../screens/task_list_screen.dart';

/// Builds the widget shown for a tab whose content varies by incident
/// category (currently just Tasks; the pattern extends to other tabs the
/// same way if/when they need it).
typedef TabScreenBuilder = Widget Function(HomeNavArgs args);

/// An extra destination surfaced under the More screen, on top of the
/// fixed items (Team Roster, Comms Plan, Med Plan, Logbook, Log Out) every
/// incident gets regardless of category.
class MoreMenuEntry {
  const MoreMenuEntry({
    required this.icon,
    required this.title,
    required this.builder,
    this.subtitle,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final TabScreenBuilder builder;
}

/// Per-category configuration: which widget the Tasks tab loads, plus any
/// extra drawer entries specific to that category (e.g. Schedule for
/// Planned Events). Resolved once per incident from `categoryForIncidentType`
/// and consumed by `AppBottomNav` (Tasks tab) and `AppDrawer` (extra
/// entries) — see AGENTS.md's rule to keep changes scoped: this is
/// deliberately a plain registry, not a server-driven config, since the
/// category itself is inferred client-side from a free-text lookup value.
class IncidentTabConfig {
  const IncidentTabConfig({
    required this.taskTabBuilder,
    this.extraMoreEntries = const [],
  });

  final TabScreenBuilder taskTabBuilder;
  final List<MoreMenuEntry> extraMoreEntries;
}

IncidentTabConfig configFor(IncidentCategory category) {
  switch (category) {
    case IncidentCategory.sar:
      return IncidentTabConfig(
        taskTabBuilder: (args) => TaskListScreen(args: args),
      );
    case IncidentCategory.plannedEvent:
      return IncidentTabConfig(
        taskTabBuilder: (args) => TaskListScreen(args: args),
        extraMoreEntries: [
          MoreMenuEntry(
            icon: Icons.event_note_outlined,
            title: 'Schedule',
            builder: (args) => ScheduleScreen(args: args),
          ),
        ],
      );
    case IncidentCategory.allHazard:
      return IncidentTabConfig(
        taskTabBuilder: (args) => TaskListScreen(args: args),
      );
  }
}
