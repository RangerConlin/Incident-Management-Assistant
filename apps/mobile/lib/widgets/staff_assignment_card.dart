import 'package:flutter/material.dart';

import '../utils/date_format.dart';
import '../utils/json_parsing.dart';
import 'section_card.dart';

/// Renders the viewer's `staff_assignments` (from `/mobile/entry` and
/// `/mobile/context`) on the Incident Staff dashboard. Hidden by the caller
/// entirely when [assignments] is empty, rather than shown empty.
class StaffAssignmentCard extends StatelessWidget {
  const StaffAssignmentCard({
    super.key,
    required this.assignments,
    this.teamName,
    this.onSwitchToTeamView,
  });

  final List<Map<String, dynamic>> assignments;

  /// The viewer's field-team name, when they also have one — shows the
  /// inline "also on a team" banner. Null/empty hides it.
  final String? teamName;
  final VoidCallback? onSwitchToTeamView;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasTeam = teamName != null && teamName!.isNotEmpty;
    return SectionCard(
      title: 'YOUR ASSIGNMENT',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final assignment in assignments) _AssignmentRow(assignment: assignment),
          if (hasTeam) ...[
            const Divider(height: 16),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Also on $teamName for this incident.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
                if (onSwitchToTeamView != null)
                  TextButton(
                    onPressed: onSwitchToTeamView,
                    child: const Text('Switch to Team View'),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _AssignmentRow extends StatelessWidget {
  const _AssignmentRow({required this.assignment});

  final Map<String, dynamic> assignment;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final title = '${assignment['title'] ?? ''}';
    final classification = '${assignment['classification'] ?? ''}';
    final assignmentType = '${assignment['assignment_type'] ?? ''}';
    final startTime = parseDateTime(assignment['start_time']);
    final metaParts = [
      if (classification.isNotEmpty) classification,
      if (startTime != null) 'since ${formatTimestamp(startTime)}',
    ];

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              if (assignmentType.isNotEmpty)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.secondaryContainer,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    assignmentType[0].toUpperCase() + assignmentType.substring(1),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSecondaryContainer,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
            ],
          ),
          if (metaParts.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                metaParts.join(' · '),
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
