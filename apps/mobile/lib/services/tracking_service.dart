import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tracelet/tracelet.dart' as tl;
import 'package:tracelet_sync/tracelet_sync.dart';

import '../config/app_config.dart';
import '../models/team_location.dart';
import 'client_connection_store.dart';
import 'sarapp_api_client.dart';

/// Background location tracking for field responders, backed by Tracelet.
///
/// Wired to the SARApp GIS Phase 1 endpoint (`POST /api/mobile/location`,
/// see "Current Mobile API Contract.txt"), which is team-level (one dot per
/// team, manual start/stop, no per-person breadcrumb trail) and identifies
/// the device by a client connection token rather than a push-notification
/// token. Push delivery is optional metadata on the connection, not the
/// identity mechanism.
///
/// Tracking is **manual, never automatic** — [start]/[stop] are driven by
/// the Settings screen's toggle, not by login/logout. The one exception is
/// [resumeIfEnabled], which restores a prior "on" state after the app is
/// killed and relaunched (it never turns tracking on from an off state).
/// See tracking_plan.md in this repo for the full design and rationale.
class TrackingService {
  TrackingService._();

  static const _enabledKey = 'tracking.enabled';
  static const _teamIdKey = 'tracking.team_id';
  static const _lastLocationKey = 'tracking.last_location';
  static const _lastHttpKey = 'tracking.last_http';
  static const _lastManualPingKey = 'tracking.last_manual_ping';
  static const _lastManualSyncKey = 'tracking.last_manual_sync';

  /// Whether the user has left tracking on, per the Settings toggle.
  /// Reflects the last successful [start]/[stop] call, not live Tracelet
  /// state.
  static Future<bool> isEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_enabledKey) ?? false;
  }

  static Future<void> _setEnabled(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_enabledKey, value);
  }

  /// The team_id the sync body builders attach to every ping — the mobile
  /// app's own signed-in team is the source of truth for team attribution
  /// server-side (see mobile_location.py), not a roster-membership lookup.
  /// Persisted (not just held in memory) so the background/headless sync
  /// builders, which run independently of any screen's widget tree, can
  /// still read it.
  static Future<void> _setTeamId(String teamId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_teamIdKey, teamId);
  }

  static Future<String?> _getTeamId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_teamIdKey);
  }

  /// Must be called once, before [start], typically right after `runApp`
  /// (or lazily before the first check-in). Registers listeners and applies
  /// the tracking [tl.Config]; does not request permissions or begin
  /// tracking — call [start] for that.
  static Future<void> initialize() async {
    if (_initialized) return;
    final existing = _initializeFuture;
    if (existing != null) return existing;
    final future = _initialize();
    _initializeFuture = future;
    try {
      await future;
      _initialized = true;
    } catch (_) {
      _initializeFuture = null;
      rethrow;
    }
  }

  static String? _configuredBaseUrl;

  /// The tracking config, including the URL locations are posted to. That URL
  /// comes from the active server connection, so [start] rebuilds the config
  /// when the connection has changed since [initialize].
  static tl.Config _buildConfig() {
    return tl.Config.balanced().copyWith(
      geo: tl.Config.balanced().geo.copyWith(
        resolveAddress: true,
        distanceFilter: 0,
        enableAdaptiveMode: false,
        disableElasticity: true,
        batteryBudgetPerHour: 0,
      ),
      motion: const tl.MotionConfig(
        motionDetectionMode: tl.MotionDetectionMode.speed,
        speedStationaryDelay:
            31536000, // ~1 year: never *transition* to stationary
        // The state machine can still *start* stationary: SpeedMotionManager
        // resumes from its persisted state (Balanced's smart mode ran this
        // same machine in earlier sessions and saved "stationary"), and the
        // emulator's 0 m/s speed can never wake it past speedMovingThreshold.
        // So make the stationary branch itself deliver the dev cadence —
        // empirically this fires like clockwork (observed exactly-120s fixes
        // with the 120 default). Both states now yield 30s: moving →
        // continuous (locationUpdateInterval 30000), stationary → periodic.
        stationaryPeriodicInterval: 30,
      ),
      // Interview: tracking should follow normal app lifecycle, not survive
      // force-kill or reboot (stopOnTerminate/startOnBoot are already the
      // library defaults — set explicitly here for clarity).
      app: const tl.AppConfig(stopOnTerminate: true, startOnBoot: false),
      android: const tl.AndroidConfig(
        locationUpdateInterval: 30000,
        fastestLocationUpdateInterval: 30000,
        allowIdenticalLocations: true,
        foregroundService: tl.ForegroundServiceConfig(
          channelName: 'Arc-Horizon Location Tracking',
          notificationTitle: 'Arc-Horizon',
          notificationText: 'Sharing your location with incident command',
        ),
      ),
      // The fused classifier is the second accelerometer consumer ("Master
      // switch. When false the classifier and accel feed never start") —
      // off along with MotionDetector. Transport-mode events return when
      // the field profile does.
      classifier: const tl.ClassifierConfig(enableFusedClassifier: false),
      http: tl.HttpConfig(
        url: '${AppConfig.sarAppBaseUrl}/api/mobile/location',
        method: tl.HttpMethod.post,
        // The backend endpoint accepts one location per request, not a
        // batch array, so batching stays off (library default).
        batchSync: false,
      ),
    );
  }

  static Future<void> _initialize() async {

    await TraceletSync.initialize();

    tl.Tracelet.onLocation((location) {
      unawaited(
        _setLastLocation(
          latitude: location.coords.latitude,
          longitude: location.coords.longitude,
          timestamp: location.timestamp,
        ),
      );
      debugPrint(
        'Tracelet location: ${location.coords.latitude}, '
        '${location.coords.longitude} (moving: ${location.isMoving})',
      );
    });

    tl.Tracelet.onModeChange((event) {
      // Placeholder — extend to surface transport-mode changes in the UI
      // (e.g. "responder left vehicle, now on foot") if command needs it.
      debugPrint(
        'Tracelet transport mode: ${event.mode} '
        '(confidence: ${event.confidence.toStringAsFixed(2)})',
      );
    });

    tl.Tracelet.onGeofence((event) {
      // Placeholder — the current backend has no geofence-event endpoint
      // (only /api/mobile/location for team position). Extend this once a
      // server-side endpoint exists, e.g. posting a narrative via
      // SarAppApiClient.postNarrative.
      debugPrint('Tracelet geofence ${event.action.name}: ${event.identifier}');
    });

    tl.Tracelet.onHttp((event) {
      unawaited(
        _setLastHttp(
          success: event.success,
          status: event.status,
          responseText: event.responseText,
          isRetry: event.isRetry,
          retryCount: event.retryCount,
        ),
      );
      debugPrint(
        'Tracelet HTTP sync: status=${event.status} '
        'success=${event.success} retry=${event.retryCount} '
        'body=${event.responseText}',
      );
    });

    await tl.Tracelet.setSyncBodyBuilder((context) async {
      final latest = context.locations.isEmpty ? null : context.locations.last;
      final coords = latest?['coords'] as Map<Object?, Object?>?;
      final connectionToken = await ClientConnectionStore.connectionToken();
      final teamId = await _getTeamId();
      return <String, Object?>{
        'connection_token': connectionToken,
        'lat': coords?['latitude'],
        'lon': coords?['longitude'],
        'timestamp': latest?['timestamp'],
        'team_id': teamId,
      };
    });

    await tl.Tracelet.registerHeadlessSyncBodyBuilder(_headlessSyncBodyBuilder);

    // DEV MODE config: fire a fix every 30s while parked, with the
    // accelerometer subsystem fully off. Five independent SDK mechanisms
    // each suppress stationary fixes and each needs its own switch — all of
    // this was confirmed by decompiling tracelet-sdk 3.5.6, not guessed:
    //
    //  1. MotionDetector (accelerometer + significant-motion listeners, the
    //     source of the "[SHAKE]/frozen accelerometer" warnings) is started
    //     for every motionDetectionMode EXCEPT `speed`. No other flag —
    //     including disableStopDetection — prevents its sensor feed.
    //  2. The speed state machine declares "stationary" after
    //     speedStationaryDelay seconds below speedMovingThreshold, and its
    //     stationary-periodic fallback runs on WorkManager PeriodicWorkRequest,
    //     which has a hard 15-MINUTE OS floor — stationaryPeriodicInterval: 30
    //     can never actually deliver 30s. So: never go stationary at all
    //     (speedStationaryDelay of ~1 year), stay in continuous mode.
    //  3. Continuous mode gates fixes on distanceFilter (Balanced: 20m) — a
    //     parked device never moves 20m, so fixes are filtered to silence.
    //     distanceFilter: 0 emits every fix.
    //  4. enableAdaptiveMode / elasticity rescale distanceFilter from
    //     activity+speed; batteryBudgetPerHour > 0 spins up a
    //     BatteryBudgetEngine that modulates sampling. All off.
    //  5. AndroidConfig.allowIdenticalLocations defaults to FALSE — fixes
    //     with coordinates identical to the previous one are dropped, which
    //     is exactly what a parked emulator produces (and what caused the
    //     "insertLocation failed: UNIQUE constraint" log spam).
    //
    // Battery cost is real (continuous GPS, no idle backoff) — this is a
    // dev-iteration profile. Restore the Balanced defaults + classifier for
    // field builds. See tracking_plan.md.
    _configuredBaseUrl = AppConfig.sarAppBaseUrl;
    final config = _buildConfig();

    // The SDK auto-resumes tracking SYNCHRONOUSLY INSIDE ready() when its
    // own persisted StateManager says tracking was enabled last session
    // (completeReady → "Resuming tracking with motion detection on
    // ready/takeover" → start()). That resume path is what hung ready() —
    // and therefore main(), on the splash screen — when speed mode was
    // first tried. This app owns resume itself (resumeIfEnabled, driven by
    // our own tracking.enabled pref), so clear the SDK's persisted enabled
    // flag first: stop() is safe pre-ready (fully null-guarded, and its
    // first action is StateManager.setEnabled(false)).
    try {
      await tl.Tracelet.stop();
    } catch (e) {
      debugPrint('TrackingService.initialize: pre-ready stop failed: $e');
    }

    await tl.Tracelet.ready(config);
  }

  static bool _initialized = false;
  static Future<void>? _initializeFuture;

  static Future<void> _retryInitialize() async {
    _initialized = false;
    _initializeFuture = null;
    await initialize();
  }

  static Future<tl.AuthorizationStatus> _requestLocationPermission() async {
    var status = await tl.Tracelet.requestLocationAuthorization();
    if (status == tl.AuthorizationStatus.whenInUse) {
      status = await tl.Tracelet.requestLocationAuthorization();
    }
    return status;
  }

  static Future<void> _setLastLocation({
    required double latitude,
    required double longitude,
    String? timestamp,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _lastLocationKey,
      '${timestamp ?? DateTime.now().toUtc().toIso8601String()} '
      '${latitude.toStringAsFixed(6)},${longitude.toStringAsFixed(6)}',
    );
  }

  static Future<void> _setLastHttp({
    required bool success,
    required int status,
    required String responseText,
    required bool isRetry,
    required int retryCount,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _lastHttpKey,
      '${DateTime.now().toUtc().toIso8601String()} '
      'status=$status success=$success retry=$isRetry/$retryCount '
      'response=$responseText',
    );
  }

  static Future<void> _setLastManualResult(String key, String result) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      key,
      '${DateTime.now().toUtc().toIso8601String()} $result',
    );
  }

  /// Dev/debug tool: fetches one location fix via Tracelet's one-shot
  /// [tl.Tracelet.getCurrentPosition] (`persist: false`, so it never touches
  /// the local SQLite queue that [start]'s background pipeline uses — this
  /// sidesteps that pipeline's flaky scheduling entirely) and POSTs it
  /// directly to `/api/mobile/location`. Requests foreground location
  /// permission if needed. Returns a human-readable result string for a
  /// SnackBar; never throws.
  static Future<String> sendManualPing({
    required String incidentId,
    required String teamId,
    required String teamName,
    required String personId,
    String? personRecord,
  }) async {
    try {
      await initialize();
      final connectionRegistered = await _registerConnectionForLocation(
        incidentId: incidentId,
        personId: personId,
        personRecord: personRecord,
        teamId: teamId,
        teamName: teamName,
      );
      if (!connectionRegistered) {
        return 'Could not register this device for location tracking. Check person_record and client connection setup.';
      }
      final connectionToken = await ClientConnectionStore.connectionToken();
      if (connectionToken == null) {
        return 'No client connection token available.';
      }
      final permission = await _requestLocationPermission();
      if (permission != tl.AuthorizationStatus.always &&
          permission != tl.AuthorizationStatus.whenInUse) {
        final message =
            'Manual ping needs location permission. Current permission: ${permission.name}.';
        await _setLastManualResult(_lastManualPingKey, message);
        return message;
      }
      late final tl.Location location;
      try {
        location = await tl.Tracelet.getCurrentPosition(persist: false);
      } on PlatformException catch (e) {
        if (e.code != 'NOT_READY') rethrow;
        await _retryInitialize();
        location = await tl.Tracelet.getCurrentPosition(persist: false);
      }
      final client = SarAppApiClient();
      try {
        final result = await client.sendLocationPing(
          connectionToken: connectionToken,
          lat: location.coords.latitude,
          lon: location.coords.longitude,
          timestamp: location.timestamp,
          teamId: teamId,
        );
        final message = 'Sent ${location.coords.latitude.toStringAsFixed(5)}, '
            '${location.coords.longitude.toStringAsFixed(5)} — '
            'server response: $result';
        await _setLastManualResult(_lastManualPingKey, message);
        return message;
      } finally {
        client.dispose();
      }
    } catch (e) {
      final message = 'Manual ping failed: $e';
      await _setLastManualResult(_lastManualPingKey, message);
      return message;
    }
  }

  /// Forces Tracelet's pending-location queue to sync now. This is diagnostic:
  /// it helps separate "no GPS records captured" from "captured but not
  /// uploaded yet".
  static Future<String> syncPendingNow() async {
    try {
      await initialize();
      final before = await tl.Tracelet.getPendingLocationCount();
      final synced = await tl.Tracelet.sync();
      final after = await tl.Tracelet.getPendingLocationCount();
      final message =
          'Manual sync complete: pending before=$before, synced=${synced.length}, pending after=$after.';
      await _setLastManualResult(_lastManualSyncKey, message);
      return message;
    } catch (e) {
      final message = 'Manual sync failed: $e';
      await _setLastManualResult(_lastManualSyncKey, message);
      return message;
    }
  }

  /// Returns the current local/native/server tracking facts for the Settings
  /// diagnostics panel.
  static Future<TrackingDiagnostics> diagnostics(String incidentId) async {
    await initialize();
    final prefs = await SharedPreferences.getInstance();
    final client = SarAppApiClient();
    try {
      tl.State? state;
      tl.ProviderChangeEvent? provider;
      int? pendingCount;
      int? serverLocationCount;
      String? error;

      try {
        state = await tl.Tracelet.getState();
      } catch (e) {
        error = 'Tracelet state failed: $e';
      }

      try {
        provider = await tl.Tracelet.getProviderState();
      } catch (e) {
        error = [
          error,
          'Provider state failed: $e',
        ].whereType<String>().join('\n');
      }

      try {
        pendingCount = await tl.Tracelet.getPendingLocationCount();
      } catch (e) {
        error = [
          error,
          'Pending count failed: $e',
        ].whereType<String>().join('\n');
      }

      try {
        serverLocationCount =
            (await client.fetchTeamLocations(incidentId)).length;
      } catch (e) {
        error = [
          error,
          'Server team-locations failed: $e',
        ].whereType<String>().join('\n');
      }

      return TrackingDiagnostics(
        toggleEnabled: prefs.getBool(_enabledKey) ?? false,
        traceletEnabled: state?.enabled,
        trackingMode: state?.trackingMode.name,
        isMoving: state?.isMoving,
        providerEnabled: provider?.enabled,
        authorizationStatus: provider?.status.name,
        gpsEnabled: provider?.gps,
        networkEnabled: provider?.network,
        pendingLocationCount: pendingCount,
        serverLocationCount: serverLocationCount,
        connectionTokenPresent:
            (await ClientConnectionStore.connectionToken())?.isNotEmpty ??
            false,
        lastLocation: prefs.getString(_lastLocationKey),
        lastHttp: prefs.getString(_lastHttpKey),
        lastManualPing: prefs.getString(_lastManualPingKey),
        lastManualSync: prefs.getString(_lastManualSyncKey),
        error: error,
      );
    } finally {
      client.dispose();
    }
  }

  /// Reads one current device fix without persisting it or posting it.
  /// Used by the map as a local fallback while the backend catches up.
  static Future<TeamLocation> currentTeamLocation({
    required String teamId,
    required String teamName,
    String? sourcePersonRecord,
    String? sourcePersonId,
  }) async {
    await initialize();
    final location = await tl.Tracelet.getCurrentPosition(persist: false);
    return TeamLocation(
      teamId: teamId,
      teamName: teamName,
      latitude: location.coords.latitude,
      longitude: location.coords.longitude,
      updatedAt:
          DateTime.tryParse(location.timestamp) ?? DateTime.now().toUtc(),
      sourcePersonRecord: sourcePersonRecord,
      sourcePersonId: sourcePersonId,
      localOnly: true,
    );
  }

  /// Requests the permissions tracking needs, sets route context, and
  /// starts location tracking. Call this from the Settings screen's
  /// tracking toggle (after the user has confirmed the explanatory
  /// dialog) or from [resumeIfEnabled].
  static Future<bool> start({
    required String incidentId,
    required String teamId,
    required String teamName,
    required String personId,
    String? personRecord,
  }) async {
    await initialize();

    await tl.Tracelet.requestNotificationAuthorization();
    await tl.Tracelet.requestMotionAuthorization();

    // Location permission escalates one step per call (not determined ->
    // when-in-use -> always), so call it twice to reach "Always", which
    // geofencing and background tracking both require.
    final status = await _requestLocationPermission();
    if (status != tl.AuthorizationStatus.always) {
      debugPrint(
        'TrackingService.start: location permission is $status, not always',
      );
      await _setEnabled(false);
      return false;
    }

    final connectionRegistered = await _registerConnectionForLocation(
      incidentId: incidentId,
      personId: personId,
      personRecord: personRecord,
      teamId: teamId,
      teamName: teamName,
    );
    if (!connectionRegistered) {
      debugPrint(
        'TrackingService.start: could not register client connection for location',
      );
      await _setEnabled(false);
      return false;
    }

    if (_configuredBaseUrl != AppConfig.sarAppBaseUrl) {
      _configuredBaseUrl = AppConfig.sarAppBaseUrl;
      await tl.Tracelet.setConfig(_buildConfig());
    }

    await tl.Tracelet.setRouteContext(
      tl.RouteContext(
        ownerId: incidentId,
        driverId: personId,
        taskId: teamId,
        startedAt: DateTime.now().toUtc().toIso8601String(),
      ),
    );

    // Persisted separately from RouteContext so the sync body builders
    // (which build our own custom payload, not Tracelet's internal context)
    // can read it independent of the widget tree — see _getTeamId.
    await _setTeamId(teamId);

    await tl.Tracelet.start();
    await _setEnabled(true);
    return true;
  }

  /// Restores tracking after the app is killed and relaunched, but only if
  /// the user had previously left it on via the Settings toggle — never
  /// starts tracking from an off state. Location permission was already
  /// granted when tracking was first enabled, so this shows no confirmation
  /// dialog; it's a resume, not a fresh opt-in.
  static Future<bool> resumeIfEnabled({
    required String incidentId,
    required String teamId,
    required String teamName,
    required String personId,
    String? personRecord,
  }) async {
    if (!await isEnabled()) return false;
    try {
      return await start(
        incidentId: incidentId,
        teamId: teamId,
        teamName: teamName,
        personId: personId,
        personRecord: personRecord,
      );
    } catch (e) {
      debugPrint('TrackingService.resumeIfEnabled failed: $e');
      await _setEnabled(false);
      return false;
    }
  }

  /// Stops location tracking, clears route context, persists the off state,
  /// and tells the server this device stopped (so a team's map dot clears
  /// immediately rather than sitting stale — see mobile_location.py's
  /// POST /api/mobile/location/stop). Call this from the Settings toggle
  /// and from logout.
  static Future<void> stop() async {
    await tl.Tracelet.clearRouteContext();
    await tl.Tracelet.stop();
    await _setEnabled(false);

    final connectionToken = await ClientConnectionStore.connectionToken();
    if (connectionToken == null) return;
    final client = SarAppApiClient();
    try {
      await client.stopMobileLocation(connectionToken);
      final deviceId = await ClientConnectionStore.deviceId();
      await client.heartbeatClientConnection(
        deviceId: deviceId,
        locationTrackingEnabled: false,
      );
    } catch (e) {
      debugPrint('TrackingService.stop: stop endpoint call failed: $e');
    } finally {
      client.dispose();
    }
  }

  /// Registers/refreshes the client connection used by location tracking.
  static Future<bool> _registerConnectionForLocation({
    required String incidentId,
    required String personId,
    required String teamId,
    required String teamName,
    String? personRecord,
  }) async {
    if (personRecord == null || personRecord.trim().isEmpty) {
      debugPrint(
        'TrackingService.start: no person_record in session; server will not accept location pings',
      );
      return false;
    }

    final client = SarAppApiClient();
    try {
      final deviceId = await ClientConnectionStore.deviceId();
      final response = await client.registerClientConnection(
        deviceId: deviceId,
        personRecord: personRecord,
        personId: personId.isEmpty ? null : personId,
        incidentId: incidentId,
        teamId: teamId,
        teamName: teamName,
        locationTrackingEnabled: true,
      );
      final connectionToken = response['connection_token'];
      if (connectionToken == null || '$connectionToken'.isEmpty) return false;
      await ClientConnectionStore.setConnectionToken('$connectionToken');
      return true;
    } catch (e) {
      debugPrint(
        'TrackingService.start: client connection registration failed: $e',
      );
      return false;
    } finally {
      client.dispose();
    }
  }

  /// Adds a circular geofence (e.g. a staging area or task boundary).
  static Future<bool> addCircularGeofence({
    required String identifier,
    required double latitude,
    required double longitude,
    required double radiusMeters,
    bool notifyOnEntry = true,
    bool notifyOnExit = true,
    bool notifyOnDwell = false,
  }) {
    return tl.Tracelet.addGeofence(
      tl.Geofence(
        identifier: identifier,
        latitude: latitude,
        longitude: longitude,
        radius: radiusMeters,
        notifyOnEntry: notifyOnEntry,
        notifyOnExit: notifyOnExit,
        notifyOnDwell: notifyOnDwell,
      ),
    );
  }

  /// Adds a polygon geofence (e.g. an irregular search-area boundary).
  /// [vertices] is a list of `[latitude, longitude]` pairs with at least 3
  /// entries; [centroidLatitude]/[centroidLongitude] are used for proximity
  /// sorting only.
  static Future<bool> addPolygonGeofence({
    required String identifier,
    required double centroidLatitude,
    required double centroidLongitude,
    required List<List<double>> vertices,
    bool notifyOnEntry = true,
    bool notifyOnExit = true,
    bool notifyOnDwell = false,
  }) {
    return tl.Tracelet.addGeofence(
      tl.Geofence(
        identifier: identifier,
        latitude: centroidLatitude,
        longitude: centroidLongitude,
        radius: 0,
        vertices: vertices,
        notifyOnEntry: notifyOnEntry,
        notifyOnExit: notifyOnExit,
        notifyOnDwell: notifyOnDwell,
      ),
    );
  }

  static Future<bool> removeGeofence(String identifier) {
    return tl.Tracelet.removeGeofence(identifier);
  }
}

/// Headless (killed-state) equivalent of [TrackingService]'s foreground sync
/// body builder. Must be a top-level function.
@pragma('vm:entry-point')
Future<void> _headlessSyncBodyBuilder(tl.HeadlessEvent event) async {
  final locations = event.event['locations'];
  Map<Object?, Object?>? latest;
  if (locations is List && locations.isNotEmpty) {
    latest = locations.last as Map<Object?, Object?>?;
  }
  final coords = latest?['coords'] as Map<Object?, Object?>?;
  final connectionToken = await ClientConnectionStore.connectionToken();
  final teamId = await TrackingService._getTeamId();
  await tl.Tracelet.setSyncBodyResponse(<String, Object?>{
    'connection_token': connectionToken,
    'lat': coords?['latitude'],
    'lon': coords?['longitude'],
    'timestamp': latest?['timestamp'],
    'team_id': teamId,
  });
}

/// The headless (killed-state) background task entry point. Registered via
/// [registerLocationHeadlessTask] before `runApp`.
@pragma('vm:entry-point')
void _headlessTaskCallback(tl.HeadlessEvent event) {
  debugPrint('Tracelet headless event: ${event.name}');
}

/// Registers the headless background task callback. Must be called before
/// `runApp`, from a `@pragma('vm:entry-point')`-eligible context (top-level
/// `main`), per Tracelet's requirements for background isolate dispatch.
Future<void> registerLocationHeadlessTask() {
  return tl.Tracelet.registerHeadlessTask(_headlessTaskCallback);
}

class TrackingDiagnostics {
  const TrackingDiagnostics({
    required this.toggleEnabled,
    required this.traceletEnabled,
    required this.trackingMode,
    required this.isMoving,
    required this.providerEnabled,
    required this.authorizationStatus,
    required this.gpsEnabled,
    required this.networkEnabled,
    required this.pendingLocationCount,
    required this.serverLocationCount,
    required this.connectionTokenPresent,
    required this.lastLocation,
    required this.lastHttp,
    required this.lastManualPing,
    required this.lastManualSync,
    required this.error,
  });

  final bool toggleEnabled;
  final bool? traceletEnabled;
  final String? trackingMode;
  final bool? isMoving;
  final bool? providerEnabled;
  final String? authorizationStatus;
  final bool? gpsEnabled;
  final bool? networkEnabled;
  final int? pendingLocationCount;
  final int? serverLocationCount;
  final bool connectionTokenPresent;
  final String? lastLocation;
  final String? lastHttp;
  final String? lastManualPing;
  final String? lastManualSync;
  final String? error;
}
