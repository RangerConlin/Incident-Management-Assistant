import 'package:shared_preferences/shared_preferences.dart';

import '../models/notification_channel.dart';

/// Persists which [NotificationSoundOption] the user picked for each
/// Android channel. Separate from [NotificationPreferences] (category
/// mute toggles) — this is "what it sounds like", not "whether I see it".
class NotificationChannelStore {
  NotificationChannelStore._();

  static String _key(String channelId) => 'notification_channel_sound.$channelId';

  /// Sensible per-severity defaults on first run: informational stays
  /// quiet, routine uses the device default, priority gets the chime,
  /// emergency gets the harder-to-miss alert tone.
  static const _defaults = {
    NotificationChannelId.informational: NotificationSoundOption.silent,
    NotificationChannelId.routine: NotificationSoundOption.defaultSound,
    NotificationChannelId.priority: NotificationSoundOption.chime,
    NotificationChannelId.emergency: NotificationSoundOption.alert,
  };

  static Future<NotificationSoundOption> soundFor(String channelId) async {
    final prefs = await SharedPreferences.getInstance();
    final storedId = prefs.getString(_key(channelId));
    if (storedId == null) {
      return _defaults[channelId] ?? NotificationSoundOption.defaultSound;
    }
    return NotificationSoundOption.byId(storedId);
  }

  static Future<void> setSoundFor(
    String channelId,
    NotificationSoundOption sound,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key(channelId), sound.id);
  }

  static Future<Map<String, NotificationSoundOption>> loadAll() async {
    final result = <String, NotificationSoundOption>{};
    for (final channelId in NotificationChannelId.all) {
      result[channelId] = await soundFor(channelId);
    }
    return result;
  }
}
