import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:ics_mobile_app/models/app_notification.dart';
import 'package:ics_mobile_app/services/notification_store.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('add stores newest-first and dedupes by id', () async {
    await NotificationStore.add(
      AppNotification(
        id: '1',
        title: 'First',
        body: '',
        severity: NotificationSeverity.routine,
        category: NotificationCategory.operations,
        receivedAt: DateTime(2026, 1, 1, 8),
      ),
    );
    await NotificationStore.add(
      AppNotification(
        id: '2',
        title: 'Second',
        body: '',
        severity: NotificationSeverity.priority,
        category: NotificationCategory.operations,
        receivedAt: DateTime(2026, 1, 1, 9),
      ),
    );
    // Re-adding id "1" with a later timestamp should replace, not duplicate.
    await NotificationStore.add(
      AppNotification(
        id: '1',
        title: 'First updated',
        body: '',
        severity: NotificationSeverity.routine,
        category: NotificationCategory.operations,
        receivedAt: DateTime(2026, 1, 1, 10),
      ),
    );

    final items = await NotificationStore.load();
    expect(items, hasLength(2));
    expect(items.first.id, '1');
    expect(items.first.title, 'First updated');
  });

  test('markRead and markAllRead flip read state without losing entries', () async {
    await NotificationStore.add(
      AppNotification(
        id: 'a',
        title: 'A',
        body: '',
        severity: NotificationSeverity.routine,
        category: NotificationCategory.communications,
        receivedAt: DateTime(2026, 1, 1),
      ),
    );
    await NotificationStore.add(
      AppNotification(
        id: 'b',
        title: 'B',
        body: '',
        severity: NotificationSeverity.routine,
        category: NotificationCategory.communications,
        receivedAt: DateTime(2026, 1, 2),
      ),
    );

    expect(await NotificationStore.unreadCount(), 2);

    await NotificationStore.markRead('b');
    expect(await NotificationStore.unreadCount(), 1);

    await NotificationStore.markAllRead();
    expect(await NotificationStore.unreadCount(), 0);
  });

  test('remove and clear drop entries', () async {
    await NotificationStore.add(
      AppNotification(
        id: 'x',
        title: 'X',
        body: '',
        severity: NotificationSeverity.emergency,
        category: NotificationCategory.safety,
        receivedAt: DateTime(2026, 1, 1),
      ),
    );
    await NotificationStore.remove('x');
    expect(await NotificationStore.load(), isEmpty);

    await NotificationStore.add(
      AppNotification(
        id: 'y',
        title: 'Y',
        body: '',
        severity: NotificationSeverity.emergency,
        category: NotificationCategory.safety,
        receivedAt: DateTime(2026, 1, 1),
      ),
    );
    await NotificationStore.clear();
    expect(await NotificationStore.load(), isEmpty);
  });
}
