import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../models/notification_channel.dart';
import 'notification_channel_store.dart';

/// Registers this app's Android notification channels — one per
/// [NotificationChannelId] — ahead of the backend actually tagging its FCM
/// messages with them. Once it does, a background/terminated-app
/// notification Android displays on its own will automatically use
/// whichever importance/sound this device already has for that channel
/// id, with nothing further to change on the mobile side.
///
/// A channel's sound is immutable once created — Android has no "update"
/// call, only delete-then-recreate-under-the-same-id — so changing the
/// user's sound choice for a channel goes through [updateSound], not a
/// second `createNotificationChannel` call.
class NotificationChannels {
  NotificationChannels._();

  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static AndroidFlutterLocalNotificationsPlugin? get _android =>
      _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin
      >();

  /// Creates every channel using whatever sound this device has stored
  /// for it (or this channel's sensible default on first run). Safe to
  /// call on every app startup — recreating a channel with identical
  /// settings is a no-op on Android.
  static Future<void> registerAll() async {
    try {
      await _plugin.initialize(
        const InitializationSettings(
          android: AndroidInitializationSettings('@mipmap/ic_launcher'),
        ),
      );
      for (final channelId in NotificationChannelId.all) {
        final sound = await NotificationChannelStore.soundFor(channelId);
        await _create(channelId, sound);
      }
    } catch (e) {
      debugPrint('NotificationChannels: registerAll failed: $e');
    }
  }

  /// Applies a new sound choice to [channelId]: persists it, then
  /// deletes and recreates the Android channel under the same id so the
  /// new sound actually takes effect for the next background/terminated
  /// notification Android displays on it.
  static Future<void> updateSound(
    String channelId,
    NotificationSoundOption sound,
  ) async {
    await NotificationChannelStore.setSoundFor(channelId, sound);
    try {
      await _android?.deleteNotificationChannel(channelId);
      await _create(channelId, sound);
    } catch (e) {
      debugPrint('NotificationChannels: updateSound($channelId) failed: $e');
    }
  }

  static Future<void> _create(
    String channelId,
    NotificationSoundOption sound,
  ) async {
    final playSound = sound.id != NotificationSoundOption.silent.id;
    await _android?.createNotificationChannel(
      AndroidNotificationChannel(
        channelId,
        NotificationChannelId.label(channelId),
        description:
            '${NotificationChannelId.label(channelId)} SARApp notifications',
        importance: _importance(NotificationChannelId.importance(channelId)),
        playSound: playSound,
        sound: sound.rawResource == null
            ? null
            : RawResourceAndroidNotificationSound(sound.rawResource!),
        enableVibration: channelId != NotificationChannelId.informational,
      ),
    );
  }

  static Importance _importance(int level) => switch (level) {
    2 => Importance.low,
    4 => Importance.high,
    5 => Importance.max,
    _ => Importance.defaultImportance,
  };
}
