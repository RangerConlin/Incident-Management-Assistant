import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:ics_mobile_app/models/notification_channel.dart';
import 'package:ics_mobile_app/services/notification_channel_store.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('unset channels fall back to their per-severity default', () async {
    expect(
      await NotificationChannelStore.soundFor(NotificationChannelId.informational),
      NotificationSoundOption.silent,
    );
    expect(
      await NotificationChannelStore.soundFor(NotificationChannelId.emergency),
      NotificationSoundOption.alert,
    );
  });

  test('setSoundFor persists and is reflected by loadAll', () async {
    await NotificationChannelStore.setSoundFor(
      NotificationChannelId.routine,
      NotificationSoundOption.silent,
    );
    final all = await NotificationChannelStore.loadAll();
    expect(all[NotificationChannelId.routine], NotificationSoundOption.silent);
    // Untouched channels keep their own defaults.
    expect(all[NotificationChannelId.priority], NotificationSoundOption.chime);
  });
}
