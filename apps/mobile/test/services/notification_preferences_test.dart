import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:ics_mobile_app/models/app_notification.dart';
import 'package:ics_mobile_app/services/notification_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('every category defaults to enabled', () async {
    final all = await NotificationPreferences.loadAll();
    expect(all, {
      for (final category in NotificationCategory.all) category: true,
    });
  });

  test('setEnabled persists and loadAll reflects it', () async {
    await NotificationPreferences.setEnabled(
      NotificationCategory.communications,
      false,
    );
    expect(
      await NotificationPreferences.isEnabled(
        NotificationCategory.communications,
      ),
      isFalse,
    );
    expect(
      await NotificationPreferences.isEnabled(NotificationCategory.operations),
      isTrue,
    );
  });
}
