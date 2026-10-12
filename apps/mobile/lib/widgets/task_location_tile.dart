import 'package:flutter/material.dart';

/// The task's free-text location field, shown verbatim — this app has no
/// structured coordinates/access-route/staging-area fields to split it
/// into, so it is deliberately displayed as-is. Styled prominently since
/// it's the most important piece of task info for the field team.
class TaskLocationTile extends StatelessWidget {
  const TaskLocationTile({super.key, required this.location});

  final String? location;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasLocation = location != null && location!.trim().isNotEmpty;
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 6),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.place, size: 24, color: theme.colorScheme.onPrimaryContainer),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              hasLocation ? location! : 'No location provided',
              style: theme.textTheme.titleMedium?.copyWith(
                color: theme.colorScheme.onPrimaryContainer,
                fontWeight: FontWeight.w700,
                fontStyle: hasLocation ? FontStyle.normal : FontStyle.italic,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
