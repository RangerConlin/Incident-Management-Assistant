import 'dart:async';

import 'package:flutter/foundation.dart';

import 'chat_service.dart';

/// Sends this device's own online/away/unavailable heartbeat to the active
/// incident's chat presence roster, mirroring the desktop client's
/// `utils/presence.py`. Started from `FieldDashboardScreen` alongside
/// `AppPresenceService`, stopped on leave-incident/logout — presence always
/// tracks whichever incident is currently open.
///
/// Status is in-memory only and always resets to "online" on `start()`,
/// matching the desktop controller resetting on every (re)connect rather
/// than persisting a stale "away" across app restarts.
class ChatPresenceService {
  ChatPresenceService._();

  static const List<String> statuses = ['online', 'away', 'unavailable'];
  static const _heartbeatInterval = Duration(seconds: 20);

  static Timer? _heartbeatTimer;
  static String? _incidentId;
  static String? _userId;

  /// Live value the roster UI listens to, so picking a new status updates
  /// the picker immediately without waiting on the network call.
  static final ValueNotifier<String> status = ValueNotifier<String>('online');

  static void start({required String incidentId, required String userId}) {
    if (userId.isEmpty) return;
    _incidentId = incidentId;
    _userId = userId;
    status.value = 'online';
    _heartbeatTimer?.cancel();
    unawaited(_sendHeartbeat());
    _heartbeatTimer = Timer.periodic(
      _heartbeatInterval,
      (_) => _sendHeartbeat(),
    );
  }

  static void setStatus(String nextStatus) {
    if (!statuses.contains(nextStatus) || nextStatus == status.value) return;
    status.value = nextStatus;
    unawaited(_sendHeartbeat());
  }

  /// Stops the heartbeat loop. Does not announce "offline" — the heartbeat
  /// simply stops, and the server's staleness window drops this user from
  /// the roster, same as the app being killed or losing connectivity.
  static void stop() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
    _incidentId = null;
    _userId = null;
  }

  static Future<void> _sendHeartbeat() async {
    final incidentId = _incidentId;
    final userId = _userId;
    if (incidentId == null || userId == null) return;
    final client = ChatService();
    try {
      await client.sendPresenceHeartbeat(
        incidentId,
        userId: userId,
        status: status.value,
      );
    } catch (e) {
      debugPrint('ChatPresenceService.heartbeat failed: $e');
    } finally {
      client.dispose();
    }
  }
}
