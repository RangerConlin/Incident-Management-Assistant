import 'package:flutter/material.dart';

import '../models/incident_context.dart';
import '../theme/app_theme.dart';

/// Compact app header: a menu button that opens the ancestor `Scaffold`'s
/// `AppDrawer`, current incident + operational period, and the field
/// team's name/status at a glance.
class IncidentHeaderBar extends StatelessWidget implements PreferredSizeWidget {
  const IncidentHeaderBar({
    super.key,
    required this.incident,
    required this.teamName,
    required this.teamStatus,
    this.onMessagesPressed,
  });

  final IncidentContext? incident;
  final String teamName;
  final String? teamStatus;
  final VoidCallback? onMessagesPressed;

  @override
  Size get preferredSize => const Size.fromHeight(96);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final incidentName = incident?.name ?? 'No active incident';
    final opPeriod = incident?.currentOperationalPeriod;
    final statusColor = teamStatus == null
        ? null
        : TeamStatusColors.forKey(
            TeamStatuses.keyForDisplayLabel(teamStatus!) ?? teamStatus!,
          );

    return AppBar(
      toolbarHeight: 96,
      leading: Builder(
        builder: (context) => IconButton(
          icon: const Icon(Icons.menu),
          tooltip: 'Menu',
          onPressed: () => Scaffold.of(context).openDrawer(),
        ),
      ),
      titleSpacing: 0,
      title: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              incidentName,
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 2),
            Text(
              opPeriod != null ? 'OP $opPeriod  ·  $teamName' : teamName,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
      actions: [
        if (teamStatus != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 4),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: statusColor!.background,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Text(
                teamStatus!,
                style: TextStyle(
                  color: statusColor.foreground,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        IconButton(
          icon: const Icon(Icons.message_outlined),
          tooltip: 'Messages',
          onPressed: onMessagesPressed,
        ),
      ],
    );
  }
}
