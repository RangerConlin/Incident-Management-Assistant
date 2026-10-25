import 'package:flutter/material.dart';

/// The Incident Staff dashboard's 2x2 "what's the incident doing right now"
/// summary: teams active, open tasks, personnel on incident, open safety
/// issues. All four are derived client-side from existing list endpoints —
/// see `IncidentStaffDashboardScreen._load`.
class IncidentStatTiles extends StatelessWidget {
  const IncidentStatTiles({
    super.key,
    required this.teamsActive,
    required this.teamsTotal,
    required this.openTasks,
    required this.personnelOnIncident,
    required this.openSafetyIssues,
  });

  final int teamsActive;
  final int teamsTotal;
  final int openTasks;
  final int personnelOnIncident;
  final int openSafetyIssues;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 2.1,
        children: [
          _StatTile(value: '$teamsActive/$teamsTotal', label: 'TEAMS ACTIVE'),
          _StatTile(value: '$openTasks', label: 'OPEN TASKS'),
          _StatTile(
            value: '$personnelOnIncident',
            label: 'PERSONNEL ON INCIDENT',
          ),
          _StatTile(
            value: '$openSafetyIssues',
            label: 'OPEN SAFETY ISSUES',
            emphasize: openSafetyIssues > 0,
          ),
        ],
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.value,
    required this.label,
    this.emphasize = false,
  });

  final String value;
  final String label;
  final bool emphasize;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              value,
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w700,
                color: emphasize ? theme.colorScheme.error : null,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
