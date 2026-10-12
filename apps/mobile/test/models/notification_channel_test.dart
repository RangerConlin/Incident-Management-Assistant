import 'package:flutter_test/flutter_test.dart';

import 'package:ics_mobile_app/models/app_notification.dart';
import 'package:ics_mobile_app/models/notification_channel.dart';

void main() {
  test('forSeverity maps every severity to its own channel', () {
    expect(
      NotificationChannelId.forSeverity(NotificationSeverity.informational),
      NotificationChannelId.informational,
    );
    expect(
      NotificationChannelId.forSeverity(NotificationSeverity.routine),
      NotificationChannelId.routine,
    );
    expect(
      NotificationChannelId.forSeverity(NotificationSeverity.priority),
      NotificationChannelId.priority,
    );
    expect(
      NotificationChannelId.forSeverity(NotificationSeverity.emergency),
      NotificationChannelId.emergency,
    );
  });

  test('importance increases from informational to emergency', () {
    final levels = [
      NotificationChannelId.informational,
      NotificationChannelId.routine,
      NotificationChannelId.priority,
      NotificationChannelId.emergency,
    ].map(NotificationChannelId.importance).toList();
    for (var i = 1; i < levels.length; i++) {
      expect(levels[i], greaterThan(levels[i - 1]));
    }
  });

  test('NotificationSoundOption.byId falls back to default for an unknown id', () {
    expect(
      NotificationSoundOption.byId('not-a-real-id'),
      NotificationSoundOption.defaultSound,
    );
    expect(
      NotificationSoundOption.byId('silent'),
      NotificationSoundOption.silent,
    );
  });
}
