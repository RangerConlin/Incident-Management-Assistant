import 'package:flutter/material.dart';

import '../models/team.dart';
import '../theme/app_theme.dart';
import 'section_card.dart';

/// Read-only, incident-wide team roster for the Incident Staff dashboard —
/// name, status chip, and current task for every team. Unlike
/// `TeamStatusGrid` (a control for setting *your own* team's status), this
/// never lets the viewer change anything; "View all" hands off to
/// `TeamManagementScreen` for that.
class TeamOverviewList extends StatelessWidget {
  const TeamOverviewList({
    super.key,
    required this.teams,
    required this.taskTitleById,
    this.ownTeamId,
    this.onViewAll,
  });

  final List<Team> teams;
  final Map<int, String> taskTitleById;

  /// The viewer's own team's `int_id`, when they have one — shows a YOU
  /// marker on that row.
  final int? ownTeamId;
  final VoidCallback? onViewAll;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SectionCard(
      title: 'TEAM STATUS',
      trailing: onViewAll == null
          ? null
          : TextButton(onPressed: onViewAll, child: const Text('View all')),
      child: teams.isEmpty
          ? Text(
              'No teams on this incident yet.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            )
          : Column(
              children: [
                for (var i = 0; i < teams.length; i++) ...[
                  if (i > 0) const Divider(height: 1),
                  _TeamRow(
                    team: teams[i],
                    taskTitle: teams[i].currentTaskId == null
                        ? null
                        : taskTitleById[teams[i].currentTaskId],
                    isOwnTeam: teams[i].intId == ownTeamId,
                  ),
                ],
              ],
            ),
    );
  }
}

class _TeamRow extends StatelessWidget {
  const _TeamRow({
    required this.team,
    required this.taskTitle,
    required this.isOwnTeam,
  });

  final Team team;
  final String? taskTitle;
  final bool isOwnTeam;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusKey = TeamStatuses.keyForDisplayLabel(team.status) ?? team.status.toLowerCase();
    final color = TeamStatusColors.forKey(statusKey);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        team.name,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ),
                    if (isOwnTeam)
                      Padding(
                        padding: const EdgeInsets.only(left: 6),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 5,
                            vertical: 1,
                          ),
                          decoration: BoxDecoration(
                            border: Border.all(color: theme.colorScheme.secondary),
                            borderRadius: BorderRadius.circular(5),
                          ),
                          child: Text(
                            'YOU',
                            style: TextStyle(
                              color: theme.colorScheme.secondary,
                              fontSize: 10,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
                if (taskTitle != null && taskTitle!.isNotEmpty)
                  Text(
                    taskTitle!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
            decoration: BoxDecoration(
              color: color.background,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              team.status,
              style: TextStyle(
                color: color.foreground,
                fontSize: 11,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
