import 'dart:async';

import 'package:flutter/foundation.dart';

import 'client_connection_store.dart';
import 'sarapp_api_client.dart';

/// Keeps this device visible in the LAN server console's "Connected
/// clients" list, independent of location tracking (see [TrackingService],
/// which registers the same `client_connections` record but only while
/// location tracking is on).
///
/// Without this, a signed-in device with tracking off never calls
/// `POST /api/client-connections/register`, so it never appears connected
/// server-side even though it's actively using the app — and the later
/// push-token `PATCH` 404s because no connection doc exists yet to patch.
class AppPresenceService {
  AppPresenceService._();

  static const _heartbeatInterval = Duration(seconds: 60);

  static Timer? _heartbeatTimer;

  /// Registers this device against the current incident/team/person and
  /// starts a periodic heartbeat so the server's staleness window
  /// (currently 120s) never lapses while the app is open. Best-effort —
  /// never throws, since presence must not block dashboard load.
  ///
  /// Safe to call every time the dashboard loads (e.g. on incident switch);
  /// re-registering just refreshes the existing connection doc.
  static Future<void> start({
    required String incidentId,
    String? teamId,
    String? teamName,
    required String personId,
    String? personRecord,
  }) async {
    _heartbeatTimer?.cancel();

    if (personRecord == null || personRecord.trim().isEmpty) {
      debugPrint(
        'AppPresenceService.start: no person_record in session; skipping registration',
      );
      return;
    }

    final client = SarAppApiClient();
    try {
      final deviceId = await ClientConnectionStore.deviceId();
      final response = await client.registerClientConnection(
        deviceId: deviceId,
        personRecord: personRecord,
        personId: personId.isEmpty ? null : personId,
        incidentId: incidentId,
        teamId: teamId ?? '',
        teamName: teamName ?? '',
      );
      final connectionToken = response['connection_token'];
      if (connectionToken != null && '$connectionToken'.isNotEmpty) {
        await ClientConnectionStore.setConnectionToken('$connectionToken');
      }
    } catch (e) {
      debugPrint('AppPresenceService.start: registration failed: $e');
    } finally {
      client.dispose();
    }

    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) => _heartbeat());
  }

  static Future<void> _heartbeat() async {
    final client = SarAppApiClient();
    try {
      final deviceId = await ClientConnectionStore.deviceId();
      await client.heartbeatClientConnection(deviceId: deviceId);
    } catch (e) {
      debugPrint('AppPresenceService.heartbeat failed: $e');
    } finally {
      client.dispose();
    }
  }

  /// Stops the heartbeat loop. Call on logout/incident switch. Does not
  /// unregister the connection doc — it will simply age out of the
  /// server's staleness window.
  static void stop() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
  }
}
