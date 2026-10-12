import 'package:flutter/material.dart';

import '../services/push_notification_service.dart';

/// Explains why the app wants to send notifications before triggering the
/// real OS permission dialog, since a denial there can't be re-prompted.
/// Marks itself as shown regardless of the user's choice, so it only
/// appears once.
Future<void> maybeShowNotificationPermissionPrompt(
  BuildContext context, {
  required Map<String, dynamic> session,
  required String incidentId,
}) async {
  if (await PushNotificationService.hasPrompted()) return;
  if (!context.mounted) return;

  final enable = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Stay notified'),
      content: const Text(
        'Enable notifications to get alerted when a task is assigned to your '
        'team or command sends an update, even when the app is in the '
        'background.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Not Now'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Enable Notifications'),
        ),
      ],
    ),
  );

  await PushNotificationService.markPrompted();
  if (enable == true) {
    final token = await PushNotificationService.requestPermissionAndGetToken();
    if (token != null) {
      final personRecord = session['person_record'];
      final personId =
          '${session['person_id'] ?? session['username'] ?? session['user_id'] ?? ''}';
      await PushNotificationService.registerToken(
        token: token,
        personRecord: personRecord == null ? null : '$personRecord',
        personId: personId.isEmpty ? null : personId,
        incidentId: incidentId,
      );
    }
  }
}
