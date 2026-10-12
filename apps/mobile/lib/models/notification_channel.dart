import 'app_notification.dart';

/// A notification's Android channel, one per [NotificationSeverity] — this
/// is the axis Android itself cares about (importance, sound, whether it
/// can bypass Do Not Disturb), as opposed to [NotificationCategory], which
/// is the axis the user mutes/unmutes by in Settings.
///
/// These ids are assumed to match what the backend will eventually set as
/// `android.notification.channel_id` on the FCM message it sends (today it
/// sets neither — see `notification_service.py` in the desktop repo). If a
/// channel with a given id already exists on the device when a message
/// tagged with it arrives, Android uses that channel's importance/sound
/// automatically for a background/terminated-app notification, with no
/// further app code involved — which is the whole point of registering
/// them ahead of that backend change rather than after it.
class NotificationChannelId {
  NotificationChannelId._();

  static const informational = 'sarapp_informational';
  static const routine = 'sarapp_routine';
  static const priority = 'sarapp_priority';
  static const emergency = 'sarapp_emergency';

  static const all = [informational, routine, priority, emergency];

  static String forSeverity(String severity) => switch (severity) {
    NotificationSeverity.informational => informational,
    NotificationSeverity.priority => priority,
    NotificationSeverity.emergency => emergency,
    _ => routine,
  };

  static String label(String channelId) => switch (channelId) {
    informational => 'Informational',
    priority => 'Priority',
    emergency => 'Emergency',
    _ => 'Routine',
  };

  /// Android importance (`NotificationChannel.IMPORTANCE_*`), 1-5. Mirrors
  /// how urgently the desktop repo's own severity table treats each level
  /// (informational never even toasts there; emergency is sticky).
  static int importance(String channelId) => switch (channelId) {
    informational => 2, // LOW — shows in the shade, no sound by default
    priority => 4, // HIGH — heads-up popup
    emergency => 5, // MAX — heads-up, can bypass Do Not Disturb
    _ => 3, // DEFAULT
  };
}

/// A sound a user can assign to a channel. `rawResource` is the Android
/// `res/raw/<name>` file (no extension) `flutter_local_notifications` reads
/// for the channel itself; `assetPath` is the matching Flutter asset this
/// app plays directly for a foreground banner/dialog, since Android only
/// plays a channel's own sound for a notification it displays itself
/// (background/terminated), not for one the app is rendering in its own UI.
class NotificationSoundOption {
  const NotificationSoundOption._(this.id, this.label, this.rawResource, this.assetPath);

  final String id;
  final String label;

  /// Null means "use the device's default notification sound" — Android
  /// handles that itself for the channel; in the foreground, this app
  /// substitutes the chime as a reasonable stand-in (see
  /// `NotificationSound`), since there's no portable way to play "the OS
  /// default sound" from Dart.
  final String? rawResource;
  final String? assetPath;

  static const defaultSound = NotificationSoundOption._(
    'default',
    'Default',
    null,
    null,
  );
  static const chime = NotificationSoundOption._(
    'chime',
    'Chime',
    'notif_chime',
    'sounds/notification_routine.wav',
  );
  static const alert = NotificationSoundOption._(
    'alert',
    'Alert',
    'notif_alert',
    'sounds/notification_emergency.wav',
  );
  static const silent = NotificationSoundOption._('silent', 'Silent', null, null);

  static const all = [defaultSound, chime, alert, silent];

  static NotificationSoundOption byId(String id) =>
      all.firstWhere((o) => o.id == id, orElse: () => defaultSound);
}
