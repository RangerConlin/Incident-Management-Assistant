import 'package:flutter/material.dart';

import '../models/narrative_entry.dart';
import '../theme/app_theme.dart';
import '../utils/date_format.dart';
import '../utils/narrative_category.dart';

/// The dominant, independently-scrollable assignment narrative feed.
/// Entries are shown newest-first, matching the API's native sort order —
/// a field responder scanning an active task wants the latest update
/// visible without scrolling.
class NarrativeFeed extends StatelessWidget {
  const NarrativeFeed({
    super.key,
    required this.entries,
    this.onRefresh,
  });

  final List<NarrativeEntry> entries;
  final Future<void> Function()? onRefresh;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    Widget list;
    if (entries.isEmpty) {
      list = ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 48),
            child: Center(
              child: Text(
                'No narrative entries yet for this task.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ),
        ],
      );
    } else {
      list = ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        itemCount: entries.length,
        separatorBuilder: (_, _) => const Divider(height: 1),
        itemBuilder: (context, index) {
          final entry = entries[index];
          return NarrativeEntryTile(
            entry: entry,
            category: categorizeNarrative(entry, entries),
          );
        },
      );
    }

    if (onRefresh == null) return list;
    return RefreshIndicator(onRefresh: onRefresh!, child: list);
  }
}

class NarrativeEntryTile extends StatelessWidget {
  const NarrativeEntryTile({super.key, required this.entry, required this.category});

  final NarrativeEntry entry;
  final NarrativeCategory category;

  Color _categoryColor() {
    switch (category) {
      case NarrativeCategory.safety:
        return TeamStatusColors.byKey['oos']!.background;
      case NarrativeCategory.assignment:
        return TeamStatusColors.byKey['arrival']!.background;
      case NarrativeCategory.update:
        return TeamStatusColors.byKey['available']!.background;
    }
  }

  IconData _categoryIcon() {
    switch (category) {
      case NarrativeCategory.safety:
        return Icons.warning_amber_rounded;
      case NarrativeCategory.assignment:
        return Icons.assignment_outlined;
      case NarrativeCategory.update:
        return Icons.info_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = _categoryColor();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(_categoryIcon(), size: 18, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      formatTimestamp(entry.timestamp),
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      category.label.toUpperCase(),
                      style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w700),
                    ),
                    if (entry.enteredBy.isNotEmpty) ...[
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          entry.enteredBy,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 3),
                Text(entry.narrative, style: theme.textTheme.bodyMedium),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
