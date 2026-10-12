import 'package:flutter_test/flutter_test.dart';

import 'package:ics_mobile_app/models/app_notification.dart';

void main() {
  test('round-trips through JSON', () {
    final original = AppNotification(
      id: 'abc',
      title: 'Task assigned',
      body: 'You have a new task',
      severity: NotificationSeverity.priority,
      category: NotificationCategory.operations,
      receivedAt: DateTime.utc(2026, 10, 11, 12, 30),
      notificationId: 42,
      incidentId: 'inc-1',
      sourceType: 'task',
      sourceId: '7',
      requiresAcknowledgement: true,
      acknowledged: false,
      data: {'task_id': '42'},
      read: true,
    );

    final decoded = AppNotification.fromJson(original.toJson());

    expect(decoded.id, original.id);
    expect(decoded.title, original.title);
    expect(decoded.body, original.body);
    expect(decoded.severity, original.severity);
    expect(decoded.category, original.category);
    expect(decoded.receivedAt, original.receivedAt);
    expect(decoded.notificationId, 42);
    expect(decoded.incidentId, 'inc-1');
    expect(decoded.sourceType, 'task');
    expect(decoded.sourceId, '7');
    expect(decoded.requiresAcknowledgement, isTrue);
    expect(decoded.data, original.data);
    expect(decoded.read, isTrue);
  });

  test('NotificationSeverity.normalize falls back to routine', () {
    expect(NotificationSeverity.normalize(null), NotificationSeverity.routine);
    expect(
      NotificationSeverity.normalize('not-a-real-severity'),
      NotificationSeverity.routine,
    );
    expect(
      NotificationSeverity.normalize('EMERGENCY'),
      NotificationSeverity.emergency,
    );
  });

  test('NotificationCategory.normalize falls back to operations', () {
    expect(NotificationCategory.normalize(null), NotificationCategory.operations);
    expect(
      NotificationCategory.normalize('not-a-real-category'),
      NotificationCategory.operations,
    );
    expect(
      NotificationCategory.normalize('SAFETY'),
      NotificationCategory.safety,
    );
  });

  test('decodeList ignores malformed JSON instead of throwing', () {
    expect(AppNotification.decodeList('not json'), isEmpty);
    expect(AppNotification.decodeList('{}'), isEmpty);
  });

  group('ToastPlan.resolve', () {
    test('informational never shows a toast, regardless of category', () {
      final plan = ToastPlan.resolve(
        severity: NotificationSeverity.informational,
        category: NotificationCategory.safety,
      );
      expect(plan.show, isFalse);
      expect(plan.sound, isFalse);
    });

    test('emergency is sticky (blocking) even for a quiet category', () {
      final plan = ToastPlan.resolve(
        severity: NotificationSeverity.emergency,
        category: NotificationCategory.administrative,
      );
      expect(plan.show, isTrue);
      expect(plan.sticky, isTrue);
    });

    test('priority extends the toast duration', () {
      final plan = ToastPlan.resolve(
        severity: NotificationSeverity.priority,
        category: NotificationCategory.operations,
      );
      expect(plan.show, isTrue);
      expect(plan.sticky, isFalse);
      expect(plan.durationMs, 7000);
    });

    test('routine administrative notification is below its own toast threshold', () {
      final plan = ToastPlan.resolve(
        severity: NotificationSeverity.routine,
        category: NotificationCategory.administrative,
      );
      expect(plan.show, isFalse);
    });
  });
}
