import 'package:flutter/material.dart';

import 'section_card.dart';

/// Tablet/landscape reference panel. This app has no GIS/live-map engine —
/// this panel is explicitly not a map. It renders whatever reference
/// material is attached to the task (image/briefing map image/document
/// preview) when that becomes available, and an honest empty state today.
class AssignmentReferencePanel extends StatelessWidget {
  const AssignmentReferencePanel({super.key, this.imageUrl});

  /// Always null today — no attachment endpoint exists yet. Kept as a
  /// parameter so a future attachment source can be wired in without
  /// reshaping this widget.
  final String? imageUrl;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SectionCard(
      title: 'REFERENCE',
      child: imageUrl != null
          ? ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.network(imageUrl!, fit: BoxFit.contain),
            )
          : Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 32),
              alignment: Alignment.center,
              child: Column(
                children: [
                  Icon(Icons.image_not_supported_outlined,
                      size: 32, color: theme.colorScheme.onSurfaceVariant),
                  const SizedBox(height: 8),
                  Text(
                    'No assignment reference attached.',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
