import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/app_notification.dart';
import 'sarapp_api_client.dart';
import 'client_connection_store.dart';
import 'notification_preferences.dart';
import 'notification_presenter.dart';
import 'notification_store.dart';
import 'session_store.dart';

/// Must be a top-level function: FCM invokes it in a separate isolate when
/// a data message arrives while the app is backgrounded or terminated.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  debugPrint('FCM background message: ${message.messageId}');
  // Best-effort: shared_preferences works via platform channel from the
  // background isolate, but this isolate has no UI and can be torn down
  // at any time, so a failure here must never surface or retry.
  try {
    await PushNotificationService._captureMessage(message);
  } catch (e) {
    debugPrint('FCM background message capture failed: $e');
  }
}

/// Wires up FCM message handling and, separately, the notification
/// permission/token flow. The permission prompt is intentionally not part
/// of app startup — see [NotificationPermissionPrompt], which gates
/// [requestPermissionAndGetToken] behind in-app explanatory UI so the OS
/// dialog (which can't be re-shown after a decline) isn't sprung on users
/// before they know why the app wants it.
class PushNotificationService {
  PushNotificationService._();

  static const _promptedKey = 'push_notification.prompted';

  static final FirebaseMessaging _messaging = FirebaseMessaging.instance;

  /// Registers listeners that don't require notification permission. Safe to
  /// call unconditionally at app startup.
  static Future<void> registerHandlers() async {
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

    FirebaseMessaging.onMessage.listen((message) async {
      debugPrint('FCM foreground message: ${message.messageId}');
      final notification = await _captureMessage(message);
      // The user is actively looking at the app right now — show it,
      // rather than leaving it to only surface next time they open the
      // drawer/Notification Center.
      if (notification != null) NotificationPresenter.present(notification);
    });

    FirebaseMessaging.onMessageOpenedApp.listen((message) async {
      debugPrint('FCM notification tapped: ${message.messageId}');
      // The user already engaged with this via the system tray, so there's
      // no need to show it again in-app — go straight to what it's about.
      final notification = await _captureMessage(message, read: true);
      if (notification != null) {
        await NotificationPresenter.openNotification(notification);
      }
    });

    // Fires at every app startup and whenever the token rotates (reinstall,
    // restore to a new device, cleared app data).
    FirebaseMessaging.instance.onTokenRefresh
        .listen((token) {
          debugPrint('FCM token refreshed: $token');
          _onTokenRefreshed(token);
        })
        .onError((err) {
          debugPrint('FCM token refresh error: $err');
        });
  }

  /// Shows the OS permission prompt and returns the device's FCM token if
  /// granted, or null if denied or unavailable (e.g. no Google Play
  /// services). Call only after the user has agreed via in-app explanatory
  /// UI.
  static Future<String?> requestPermissionAndGetToken() async {
    final settings = await _messaging.requestPermission();
    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      debugPrint('Push notification permission denied');
      return null;
    }

    try {
      final token = await _messaging.getToken();
      debugPrint('FCM token: $token');
      return token;
    } catch (e) {
      debugPrint('Failed to fetch FCM token: $e');
      return null;
    }
  }

  /// Whether the in-app explanatory prompt has already been shown once.
  static Future<bool> hasPrompted() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_promptedKey) ?? false;
  }

  static Future<void> markPrompted() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_promptedKey, true);
  }

  /// Whether the OS has already granted notification permission. Checks
  /// current status only — never prompts.
  static Future<bool> hasPermission() async {
    final settings = await _messaging.getNotificationSettings();
    return settings.authorizationStatus == AuthorizationStatus.authorized ||
        settings.authorizationStatus == AuthorizationStatus.provisional;
  }

  /// Sends [token] to the backend for the given person/incident. Best-effort
  /// — failures are logged, never thrown, since this must not block login,
  /// dashboard load, or logout.
  static Future<void> registerToken({
    required String token,
    String? personRecord,
    String? personId,
    required String incidentId,
  }) async {
    final client = SarAppApiClient();
    try {
      final deviceId = await ClientConnectionStore.deviceId();
      try {
        await client.updateClientConnectionPushToken(
          deviceId: deviceId,
          fcmToken: token,
          notificationPermission: 'authorized',
        );
        return;
      } catch (e) {
        debugPrint('Client connection push-token update failed: $e');
      }
      await client.registerPushToken(
        token: token,
        personRecord: personRecord,
        personId: personId,
        incidentId: incidentId,
      );
    } catch (e) {
      debugPrint('Push token registration failed: $e');
    } finally {
      client.dispose();
    }
  }

  /// Re-registers the current device token with the given person/incident
  /// IF permission was already granted (never prompts). Call this on every
  /// login/session-restore — it's how a shared/handoff device gets
  /// re-associated to whichever person is currently logged in, independent
  /// of the one-time explanatory dialog.
  static Future<void> syncRegistration({
    String? personRecord,
    String? personId,
    required String incidentId,
  }) async {
    String? token;
    try {
      if (!await hasPermission()) return;
      token = await _messaging.getToken();
    } catch (e) {
      debugPrint('syncRegistration: failed to fetch FCM token: $e');
      return;
    }
    if (token == null) return;
    await registerToken(
      token: token,
      personRecord: personRecord,
      personId: personId,
      incidentId: incidentId,
    );
  }

  /// Best-effort server-side unregistration of this device's current token.
  /// Call before clearing the local session on logout.
  static Future<void> unregisterCurrentToken() async {
    String? token;
    try {
      token = await _messaging.getToken();
    } catch (e) {
      debugPrint('unregisterCurrentToken: failed to fetch token: $e');
      return;
    }
    if (token == null) return;
    final client = SarAppApiClient();
    try {
      await client.unregisterPushToken(token);
    } catch (e) {
      debugPrint('Push token unregistration failed: $e');
    } finally {
      client.dispose();
    }
  }

  /// Files [message] into the on-device notification history
  /// ([NotificationStore]), honoring the user's per-category preference
  /// ([NotificationPreferences]) — except a `priority`/`emergency`
  /// severity always gets stored, since a category mute is meant for
  /// routine chatter, not for something urgent enough to warrant that
  /// severity in the first place. Returns the stored entry (for the
  /// caller to decide whether/how to present it), or null if it was
  /// filtered out.
  ///
  /// Expects the full, correct payload the server-side notification
  /// system is documented to send (see `notifications.py`/
  /// `notification_service.py` in the desktop repo and this repo's
  /// `Current Mobile API Contract.txt`): `data` carrying
  /// `notification_id`, `incident_id`, `severity`, `category`,
  /// `source_type`, `source_id`, and `requires_acknowledgement`.
  static Future<AppNotification?> _captureMessage(
    RemoteMessage message, {
    bool read = false,
  }) async {
    final data = message.data;
    final severity = NotificationSeverity.normalize(data['severity'] as String?);
    final category = NotificationCategory.normalize(data['category'] as String?);

    final mutable = NotificationSeverity.rank(severity) <
        NotificationSeverity.rank(NotificationSeverity.priority);
    if (mutable && !await NotificationPreferences.isEnabled(category)) {
      return null;
    }

    final title =
        message.notification?.title ?? data['title'] as String? ?? 'Notification';
    final body =
        message.notification?.body ?? data['body'] as String? ?? '';
    final id =
        message.messageId ?? 'local-${DateTime.now().microsecondsSinceEpoch}';

    final notification = AppNotification(
      id: id,
      title: title,
      body: body,
      severity: severity,
      category: category,
      receivedAt: DateTime.now(),
      notificationId: data['notification_id'] == null
          ? null
          : int.tryParse('${data['notification_id']}'),
      incidentId: data['incident_id'] as String?,
      sourceType: data['source_type'] as String?,
      sourceId: data['source_id'] as String?,
      requiresAcknowledgement: '${data['requires_acknowledgement']}' == 'true',
      data: data,
      read: read,
    );
    await NotificationStore.add(notification);
    return notification;
  }

  /// Re-registers on token rotation using whatever session is currently
  /// persisted, since a refresh can fire before any UI — and therefore any
  /// BuildContext/session argument — exists.
  static Future<void> _onTokenRefreshed(String token) async {
    final saved = await SessionStore.load();
    if (saved == null) return;
    final session = saved.session;
    final personRecord = session['person_record'];
    final personId =
        '${session['person_id'] ?? session['username'] ?? session['user_id'] ?? ''}';
    await registerToken(
      token: token,
      personRecord: personRecord == null ? null : '$personRecord',
      personId: personId.isEmpty ? null : personId,
      incidentId: saved.incidentId,
    );
  }
}
