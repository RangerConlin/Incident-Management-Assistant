import 'package:shared_preferences/shared_preferences.dart';

import '../models/app_notification.dart';

/// Device-local notification history (in-app inbox). Not server-synced —
/// entries are captured on this device as FCM messages arrive, so history
/// does not follow the user to a different device or survive a reinstall.
class NotificationStore {
  NotificationStore._();

  static const _storageKey = 'notification_store.items';

  /// Oldest entries are dropped past this count so the stored JSON blob
  /// can't grow unbounded on a device that's never cleared its history.
  static const _maxEntries = 200;

  static Future<List<AppNotification>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_storageKey);
    if (raw == null) return [];
    final items = AppNotification.decodeList(raw);
    items.sort((a, b) => b.receivedAt.compareTo(a.receivedAt));
    return items;
  }

  static Future<void> _save(List<AppNotification> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, AppNotification.encodeList(items));
  }

  /// Adds [notification], newest-first. A duplicate `id` (e.g. the opened-app
  /// handler firing for a message the foreground handler already captured)
  /// replaces the existing entry instead of duplicating it.
  static Future<void> add(AppNotification notification) async {
    final items = await load();
    items.removeWhere((e) => e.id == notification.id);
    items.insert(0, notification);
    if (items.length > _maxEntries) {
      items.removeRange(_maxEntries, items.length);
    }
    await _save(items);
  }

  static Future<void> markRead(String id) async {
    final items = await load();
    final index = items.indexWhere((e) => e.id == id);
    if (index == -1) return;
    items[index] = items[index].copyWith(read: true);
    await _save(items);
  }

  static Future<void> markAllRead() async {
    final items = await load();
    await _save([for (final e in items) e.copyWith(read: true)]);
  }

  static Future<void> remove(String id) async {
    final items = await load();
    items.removeWhere((e) => e.id == id);
    await _save(items);
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_storageKey);
  }

  static Future<int> unreadCount() async {
    final items = await load();
    return items.where((e) => !e.read).length;
  }
}
