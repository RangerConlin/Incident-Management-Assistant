import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../models/notification_channel.dart';
import 'notification_channel_store.dart';

/// Foreground-only sound/haptic feedback for an in-app notification
/// banner or the emergency dialog, using whatever sound the user picked
/// for that severity's channel in Settings ([NotificationChannelStore]) —
/// the same choice that governs the channel's sound for a background/
/// terminated-app notification, so the two cases feel consistent.
///
/// Android only plays a channel's own sound for a notification it
/// displays itself; a banner/dialog this app renders in its own UI has to
/// play that sound itself, which is what this does. "Default (system)"
/// has no portable Dart equivalent to "play the OS's own default
/// notification sound", so the chime stands in for it here.
class NotificationSound {
  NotificationSound._();

  static final AudioPlayer _player = AudioPlayer();

  static Future<void> play(String severity) async {
    final channelId = NotificationChannelId.forSeverity(severity);
    final sound = await NotificationChannelStore.soundFor(channelId);
    final isEmergency = channelId == NotificationChannelId.emergency;

    try {
      unawaited(
        isEmergency
            ? HapticFeedback.heavyImpact()
            : HapticFeedback.mediumImpact(),
      );
      if (sound.id == NotificationSoundOption.silent.id) return;
      final assetPath =
          sound.assetPath ?? NotificationSoundOption.chime.assetPath!;
      await _player.play(AssetSource(assetPath));
    } catch (e) {
      debugPrint('NotificationSound: playback failed: $e');
    }
  }
}
