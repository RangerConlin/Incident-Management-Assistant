import 'package:flutter/material.dart';

import '../models/app_notification.dart';

/// Visual content of an in-app notification banner — ported look from the
/// desktop repo's toast (`notifications/widgets/toast_manager.py`): a left
/// accent bar colored by severity, an optional category chip, title/body,
/// and a close button. Positioning/insertion into an `Overlay` is handled
/// by whoever shows this (see `NotificationPresenter`), not by this widget.
class NotificationBannerCard extends StatelessWidget {
  const NotificationBannerCard({
    super.key,
    required this.notification,
    required this.onTap,
    required this.onDismiss,
  });

  final AppNotification notification;
  final VoidCallback onTap;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final accent = Color(
      NotificationSeverity.accentColorValue(notification.severity),
    );
    final categoryColor = Color(
      NotificationCategory.accentColorValue(notification.category),
    );
    final categoryShort = NotificationCategory.shortLabel(notification.category);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          constraints: const BoxConstraints(maxWidth: 420),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHigh,
            borderRadius: BorderRadius.circular(8),
            border: Border(left: BorderSide(color: accent, width: 3)),
            boxShadow: const [
              BoxShadow(color: Colors.black38, blurRadius: 8, offset: Offset(0, 2)),
            ],
          ),
          padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  if (categoryShort.isNotEmpty) ...[
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 4,
                        vertical: 1,
                      ),
                      decoration: BoxDecoration(
                        border: Border.all(color: categoryColor),
                        borderRadius: BorderRadius.circular(3),
                      ),
                      child: Text(
                        categoryShort,
                        style: TextStyle(
                          color: categoryColor,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    const SizedBox(width: 6),
                  ],
                  Expanded(
                    child: Text(
                      notification.title,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, size: 18),
                    constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                    padding: EdgeInsets.zero,
                    onPressed: onDismiss,
                  ),
                ],
              ),
              if (notification.body.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(
                    notification.body,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
