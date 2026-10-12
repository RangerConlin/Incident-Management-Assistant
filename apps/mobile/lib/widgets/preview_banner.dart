import 'package:flutter/material.dart';

/// Banner shown at the top of screens whose content is sample/placeholder
/// data rather than a live server fetch, so it's never mistaken for real
/// field data (see AGENTS.md: never fabricate live records).
class PreviewBanner extends StatelessWidget {
  const PreviewBanner({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      color: theme.colorScheme.secondaryContainer,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Icon(Icons.visibility_outlined, size: 16, color: theme.colorScheme.onSecondaryContainer),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSecondaryContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
