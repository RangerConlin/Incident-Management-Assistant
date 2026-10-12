import 'package:shared_preferences/shared_preferences.dart';

import '../models/app_notification.dart';

/// Per-category opt-in for the in-app notification history. This is a local
/// filter only — it decides whether an incoming FCM message gets filed into
/// [NotificationStore], not whether the OS shows a system notification for
/// it (that's governed by OS/channel settings and, eventually, by whatever
/// a server-side send actually targets). Every category defaults to on.
class NotificationPreferences {
  NotificationPreferences._();

  static String _key(String category) => 'notification_prefs.$category';

  static Future<bool> isEnabled(String category) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_key(category)) ?? true;
  }

  static Future<void> setEnabled(String category, bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key(category), value);
  }

  /// All known categories mapped to their current enabled state, in the
  /// order they should be displayed.
  static Future<Map<String, bool>> loadAll() async {
    final result = <String, bool>{};
    for (final category in NotificationCategory.all) {
      result[category] = await isEnabled(category);
    }
    return result;
  }
}
