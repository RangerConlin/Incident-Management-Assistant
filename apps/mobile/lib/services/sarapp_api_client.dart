import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../models/geocode_result.dart';
import '../models/incident_alert.dart';
import '../models/ics205_plan.dart';
import '../models/ics206_plan.dart';
import '../models/mobile_incident_context.dart';
import '../models/team_location.dart';
import 'local_profile_store.dart';

enum PersonLookupStatus { found, notFound, ambiguous }

/// Result of matching a login ID to the personnel roster.
class PersonLookup {
  const PersonLookup({required this.status, this.name});

  factory PersonLookup.fromJson(Map<String, dynamic> json) {
    final status = switch (json['status']) {
      'found' => PersonLookupStatus.found,
      'ambiguous' => PersonLookupStatus.ambiguous,
      _ => PersonLookupStatus.notFound,
    };
    final person = json['person'];
    final name = person is Map ? '${person['name'] ?? ''}'.trim() : '';
    return PersonLookup(status: status, name: name.isEmpty ? null : name);
  }

  final PersonLookupStatus status;

  /// The matched person's full name; null unless [status] is found.
  final String? name;
}

class SarAppApiException implements Exception {
  SarAppApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => 'SarAppApiException($statusCode): $message';
}

/// Thin HTTP client for the SARApp cloud server, scoped to the endpoints
/// documented in "Current Mobile API Contract.txt".
class SarAppApiClient {
  SarAppApiClient({http.Client? httpClient, String? baseUrl})
    : _httpClient = httpClient ?? http.Client(),
      baseUrl = baseUrl ?? AppConfig.sarAppBaseUrl;

  final http.Client _httpClient;
  final String baseUrl;

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    return Uri.parse('$baseUrl$path').replace(
      queryParameters: query?.map((key, value) => MapEntry(key, '$value')),
    );
  }

  Future<Map<String, dynamic>> _getJson(
    String path, [
    Map<String, dynamic>? query,
  ]) async {
    final response = await _httpClient.get(_uri(path, query));
    return _decodeJsonObject(response);
  }

  Future<Map<String, dynamic>> _postJson(
    String path, {
    Map<String, dynamic>? query,
    Map<String, dynamic>? body,
  }) async {
    final response = await _httpClient.post(
      _uri(path, query),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode(body ?? const <String, dynamic>{}),
    );
    return _decodeJsonObject(response);
  }

  Future<Map<String, dynamic>> _putJson(
    String path, {
    Map<String, dynamic>? query,
    Map<String, dynamic>? body,
  }) async {
    final response = await _httpClient.put(
      _uri(path, query),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode(body ?? const <String, dynamic>{}),
    );
    return _decodeJsonObject(response);
  }

  Future<Map<String, dynamic>> _patchJson(
    String path, {
    Map<String, dynamic>? query,
    Map<String, dynamic>? body,
  }) async {
    final response = await _httpClient.patch(
      _uri(path, query),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode(body ?? const <String, dynamic>{}),
    );
    return _decodeJsonObject(response);
  }

  Future<void> _delete(String path, [Map<String, dynamic>? query]) async {
    final response = await _httpClient.delete(_uri(path, query));
    _decode(response);
  }

  Future<List<dynamic>> _getJsonList(
    String path, [
    Map<String, dynamic>? query,
  ]) async {
    final response = await _httpClient.get(_uri(path, query));
    final decoded = _decode(response);
    if (decoded is List) return decoded;
    if (decoded is Map && decoded['items'] is List) {
      return decoded['items'] as List;
    }
    throw SarAppApiException('Expected a list response from $path');
  }

  dynamic _decode(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SarAppApiException(
        _errorDetail(response) ?? 'Request to ${response.request?.url} failed',
        statusCode: response.statusCode,
      );
    }
    if (response.body.isEmpty) return <String, dynamic>{};
    return jsonDecode(response.body);
  }

  /// The server's human-readable `detail` message for an error response, if
  /// it sent one as a plain string.
  String? _errorDetail(http.Response response) {
    try {
      final body = jsonDecode(response.body);
      if (body is Map && body['detail'] is String) {
        final detail = (body['detail'] as String).trim();
        if (detail.isNotEmpty) return detail;
      }
    } catch (_) {}
    return null;
  }

  Map<String, dynamic> _decodeJsonObject(http.Response response) {
    final decoded = _decode(response);
    if (decoded is Map<String, dynamic>) return decoded;
    throw SarAppApiException('Expected a JSON object response');
  }

  /// Health check used as the mobile app's connection/session gate, since
  /// the server does not yet expose a mobile auth endpoint.
  Future<bool> checkHealth() async {
    try {
      final response = await _httpClient.get(_uri('/health'));
      return response.statusCode >= 200 && response.statusCode < 300;
    } catch (_) {
      return false;
    }
  }

  Future<List<dynamic>> fetchIncidents() => _getJsonList('/api/incidents');

  Future<Map<String, dynamic>> fetchIncidentHeader(String incidentId) =>
      _getJson('/api/incidents/$incidentId/header');

  Future<Map<String, dynamic>> fetchIncidentProfile(String incidentId) =>
      _getJson('/api/incidents/$incidentId/profile');

  Future<List<dynamic>> fetchCheckinRoles(String incidentId) =>
      _getJsonList('/api/incidents/$incidentId/checkin/roles');

  Future<List<dynamic>> fetchCheckinRoster(String incidentId) =>
      _getJsonList('/api/incidents/$incidentId/checkin/roster');

  Future<List<dynamic>> searchPersonnel(
    String incidentId, {
    String query = '',
    int limit = 50,
  }) => _getJsonList('/api/incidents/$incidentId/checkin/personnel/search', {
    'q': query,
    'limit': limit,
  });

  Future<Map<String, dynamic>> fetchCheckin(
    String incidentId,
    String personRecord,
  ) => _getJson('/api/incidents/$incidentId/checkin/$personRecord');

  Future<MobileIncidentContext> enterIncident({
    required String incidentId,
    required int personRecord,
    String? teamId,
  }) async {
    final parsedTeamId = teamId == null || teamId.isEmpty
        ? null
        : int.tryParse(teamId);
    return MobileIncidentContext.fromJson(
      await _postJson(
        '/api/incidents/$incidentId/mobile/entry',
        body: {'person_record': personRecord, 'team_id': ?parsedTeamId},
      ),
    );
  }

  Future<MobileIncidentContext> fetchMobileIncidentContext({
    required String incidentId,
    required int personRecord,
  }) async => MobileIncidentContext.fromJson(
    await _getJson('/api/incidents/$incidentId/mobile/context/$personRecord'),
  );

  /// Checks a login ID against the personnel roster. The result's status says
  /// whether the ID matched exactly one record, none (offer to create one) or
  /// several (cannot sign in).
  Future<PersonLookup> lookupPerson(String personId) async =>
      PersonLookup.fromJson(
        await _getJson('/api/auth/lookup', {'person_id': personId}),
      );

  /// Creates the personnel record for a profile whose ID has none yet.
  Future<PersonLookup> registerPerson(LocalProfile profile) async =>
      PersonLookup.fromJson(
        await _postJson('/api/auth/register', body: profile.toJson()),
      );

  /// Applies the device's profile to the existing personnel (master) record
  /// with the same Person ID. The server overwrites with each non-blank
  /// field; blank fields never clear stored values.
  Future<PersonLookup> updateProfile(LocalProfile profile) async =>
      PersonLookup.fromJson(
        await _putJson('/api/auth/profile', body: profile.toJson()),
      );

  /// Starts a login session the same way the desktop client does via
  /// `POST /api/auth/sessions`. The desktop convention (see
  /// `modules/login_dialog.py`) is that the username *is* the operator's
  /// person_id; password is not validated server-side.
  Future<Map<String, dynamic>> startSession({
    required String personId,
    required String incidentId,
    String? role,
  }) async {
    final response = await _httpClient.post(
      _uri('/api/auth/sessions'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'username': personId,
        'incident_id': incidentId,
        'role': role ?? 'Field User',
        'status': 'online',
      }),
    );
    return _decodeJsonObject(response);
  }

  Future<Map<String, dynamic>> submitCheckin({
    required String incidentId,
    required String personId,
    required Map<String, dynamic> checkinPayload,
  }) => _putJson(
    '/api/incidents/$incidentId/checkin/$personId',
    body: checkinPayload,
  );

  Future<Map<String, dynamic>> patchCheckin({
    required String incidentId,
    required String personId,
    required Map<String, dynamic> checkinPayload,
  }) => _patchJson(
    '/api/incidents/$incidentId/checkin/$personId',
    body: checkinPayload,
  );

  /// Operations-module team list — has each team's `int_id`, which is the id
  /// the status/task endpoints below actually key off of (distinct from the
  /// check-in module's own `team_id` field; see field-dashboard plan notes).
  Future<List<dynamic>> fetchTeams(String incidentId) =>
      _getJsonList('/api/incidents/$incidentId/operations/teams');

  Future<List<TeamLocation>> fetchTeamLocations(String incidentId) async {
    final rows = await _getJsonList(
      '/api/incidents/$incidentId/team-locations',
    );
    return rows
        .whereType<Map>()
        .map((row) => TeamLocation.fromJson(Map<String, dynamic>.from(row)))
        .where((location) => location.teamId.isNotEmpty)
        .toList();
  }

  Future<GeocodeResult> geocode(String query) async {
    final response = await _httpClient.post(
      _uri('/api/geocoding/geocode'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'address': query}),
    );
    return GeocodeResult.fromJson(_decodeJsonObject(response));
  }

  Future<Map<String, dynamic>> fetchTeam(String incidentId, String teamIntId) =>
      _getJson('/api/incidents/$incidentId/operations/teams/$teamIntId');

  Future<Map<String, dynamic>> updateTeam({
    required String incidentId,
    required String teamIntId,
    required Map<String, dynamic> body,
  }) => _patchJson(
    '/api/incidents/$incidentId/operations/teams/$teamIntId',
    body: body,
  );

  Future<void> deleteTeam({
    required String incidentId,
    required String teamIntId,
  }) => _delete('/api/incidents/$incidentId/operations/teams/$teamIntId');

  Future<Map<String, dynamic>> fetchTask(String incidentId, String taskId) =>
      _getJson('/api/incidents/$incidentId/operations/tasks/$taskId');

  Future<List<dynamic>> fetchTasks(String incidentId) =>
      _getJsonList('/api/incidents/$incidentId/operations/tasks');

  /// Acknowledges a notification that was flagged
  /// `requires_acknowledgement` (e.g. an emergency broadcast), so command
  /// can see who has and hasn't responded.
  Future<Map<String, dynamic>> acknowledgeNotification({
    required String incidentId,
    required int notificationId,
    required int personRecord,
  }) => _postJson(
    '/api/incidents/$incidentId/notifications/$notificationId/acknowledge',
    body: {'person_record': personRecord},
  );

  /// Dismisses a notification without acknowledging it — used for the
  /// in-app banner/dialog's "Dismiss" action on notifications that don't
  /// require an explicit acknowledgement.
  Future<Map<String, dynamic>> dismissNotification({
    required String incidentId,
    required int notificationId,
    required int personRecord,
  }) => _postJson(
    '/api/incidents/$incidentId/notifications/$notificationId/dismiss',
    body: {'person_record': personRecord},
  );

  Future<List<IncidentAlert>> fetchAlerts(String incidentId) async {
    final rows = await _getJsonList('/api/incidents/$incidentId/alerts');
    return rows
        .whereType<Map>()
        .map((row) => IncidentAlert.fromJson(Map<String, dynamic>.from(row)))
        .toList();
  }

  Future<List<dynamic>> fetchIncidentResources(
    String incidentId, {
    String resourceType = '',
  }) => _getJsonList('/api/incidents/$incidentId/resources', {
    if (resourceType.isNotEmpty) 'resource_type': resourceType,
  });

  Future<List<dynamic>> fetchResourceStatuses(
    String incidentId, {
    String entityType = '',
    String status = '',
  }) => _getJsonList('/api/incidents/$incidentId/resource-status', {
    if (entityType.isNotEmpty) 'entity_type': entityType,
    if (status.isNotEmpty) 'status': status,
  });

  Future<Map<String, dynamic>> upsertIncidentResourceStatus({
    required String incidentId,
    required Map<String, dynamic> body,
  }) => _postJson('/api/incidents/$incidentId/resource-status', body: body);

  Future<Map<String, dynamic>> patchIncidentResource({
    required String incidentId,
    required String itemId,
    required Map<String, dynamic> body,
  }) => _patchJson(
    '/api/incidents/$incidentId/resource-status/$itemId',
    body: body,
  );

  Future<Map<String, dynamic>> patchIncidentResourceStatus({
    required String incidentId,
    required String itemId,
    required Map<String, dynamic> body,
  }) => _patchJson(
    '/api/incidents/$incidentId/resource-status/$itemId/status',
    body: body,
  );

  Future<List<dynamic>> fetchMasterVehicles({
    String search = '',
    String statusFilter = '',
    String typeFilter = '',
  }) => _getJsonList('/api/master/vehicles', {
    if (search.isNotEmpty) 'search': search,
    if (statusFilter.isNotEmpty) 'status_filter': statusFilter,
    if (typeFilter.isNotEmpty) 'type_filter': typeFilter,
  });

  Future<List<dynamic>> fetchMasterAircraft({
    String search = '',
    String status = '',
    String typeFilter = '',
  }) => _getJsonList('/api/master/aircraft', {
    if (search.isNotEmpty) 'search': search,
    if (status.isNotEmpty) 'status': status,
    if (typeFilter.isNotEmpty) 'type_filter': typeFilter,
  });

  Future<List<dynamic>> fetchMasterEquipment({
    String search = '',
    int limit = 200,
  }) => _getJsonList('/api/master/equipment', {
    if (search.isNotEmpty) 'search': search,
    'limit': limit,
  });

  /// The hardcoded organization hierarchy (see
  /// `sarapp_db.org_data`/`organizations.py` on the server) — used to
  /// populate and keep in sync the profile screen's organization picker.
  Future<List<dynamic>> fetchMasterOrganizations() =>
      _getJsonList('/api/master/organizations');

  Future<List<dynamic>> fetchTeamTypes() =>
      _getJsonList('/api/lookup/team-types');

  /// Ranks for one rank structure, or every structure if [structureKey] is
  /// omitted.
  Future<List<dynamic>> fetchMasterRanks({String structureKey = ''}) =>
      _getJsonList('/api/master/ranks', {
        if (structureKey.isNotEmpty) 'structure_key': structureKey,
      });

  Future<List<dynamic>> fetchNarratives(
    String incidentId, {
    int? taskId,
    String? search,
    bool? criticalOnly,
    String? team,
  }) => _getJsonList('/api/incidents/$incidentId/narratives', {
    'task_id': ?taskId,
    if (search != null && search.isNotEmpty) 'search': search,
    'critical_only': ?criticalOnly,
    if (team != null && team.isNotEmpty) 'team': team,
  });

  Future<Map<String, dynamic>> postNarrative({
    required String incidentId,
    required int taskId,
    required String narrative,
    required String enteredBy,
    String teamNum = '',
    bool critical = false,
  }) async {
    final response = await _httpClient.post(
      _uri('/api/incidents/$incidentId/narratives'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'task_id': taskId,
        'timestamp': DateTime.now().toUtc().toIso8601String(),
        'narrative': narrative,
        'entered_by': enteredBy,
        'team_num': teamNum,
        'critical': critical ? 1 : 0,
      }),
    );
    return _decodeJsonObject(response);
  }

  /// The team's ICS 214 log. The server creates the team's stream on first
  /// use and omits internal (composition) entries. [since] is an ISO
  /// timestamp for delta polling.
  Future<List<dynamic>> fetchTeamLog(
    String incidentId,
    String teamIntId, {
    String? since,
  }) => _getJsonList('/api/incidents/$incidentId/mobile/teams/$teamIntId/log', {
    'since': ?since,
  });

  Future<Map<String, dynamic>> postTeamLogEntry({
    required String incidentId,
    required String teamIntId,
    required String text,
    required String actorUserId,
    bool critical = false,
  }) => _postJson(
    '/api/incidents/$incidentId/mobile/teams/$teamIntId/log',
    body: {
      'text': text,
      'actor_user_id': actorUserId,
      'timestamp_utc': DateTime.now().toUtc().toIso8601String(),
      'critical_flag': critical,
    },
  );

  Future<Map<String, dynamic>> patchTeamStatus({
    required String incidentId,
    required String teamIntId,
    required String statusKey,
    required String changedBy,
  }) async {
    final response = await _httpClient.patch(
      _uri('/api/incidents/$incidentId/operations/teams/$teamIntId/status'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'status_key': statusKey, 'changed_by': changedBy}),
    );
    return _decodeJsonObject(response);
  }

  /// Best-effort "current" operational period: the backend only exposes the
  /// full list of known op-period numbers, not a single "active" one, so
  /// callers should treat `max(result)` as an approximation.
  Future<List<dynamic>> fetchOpPeriods(String incidentId) =>
      _getJsonList('/api/incidents/$incidentId/op-periods');

  /// Active hazards for the Incident Staff dashboard's safety-issue count.
  /// [opPeriod] is the plain operational-period number (matching
  /// [fetchOpPeriods]), not an internal document id.
  Future<List<dynamic>> fetchHazards(String incidentId, {int? opPeriod}) =>
      _getJsonList('/api/incidents/$incidentId/safety/hazards', {
        'op_period': ?opPeriod,
      });

  /// IC objectives for the Incident Staff dashboard. Deliberately not
  /// filtered by operational period here — the objectives router's
  /// `op_period_id` expects an internal planning-period id, not the plain
  /// period number [fetchOpPeriods] returns, so callers that only have the
  /// latter should leave this unset rather than filter on the wrong value.
  Future<List<dynamic>> fetchObjectives(
    String incidentId, {
    String? opPeriodId,
  }) => _getJsonList('/api/objectives', {
    'incident_id': incidentId,
    'op_period_id': ?opPeriodId,
  });

  Future<Ics205Plan> fetchIcs205Plan(String incidentId, {int? opPeriod}) async {
    final query = {'op_period_id': ?opPeriod};
    final results = await Future.wait<dynamic>([
      _getJsonList('/api/incidents/$incidentId/channels-plan'),
      _getJson('/api/incidents/$incidentId/communications-plan', query),
    ]);

    return Ics205Plan.fromJson(
      channelRows: results[0] as List<dynamic>,
      planJson: results[1] as Map<String, dynamic>,
    );
  }

  Future<Ics206Plan> fetchIcs206Plan(String incidentId, {int? opPeriod}) async {
    final query = {'op': ?opPeriod};
    final results = await Future.wait<dynamic>([
      _getJsonList(
        '/api/incidents/$incidentId/medical/ics206/aid-stations',
        query,
      ),
      _getJsonList(
        '/api/incidents/$incidentId/medical/ics206/ambulance-services',
        query,
      ),
      _getJsonList(
        '/api/incidents/$incidentId/medical/ics206/hospitals',
        query,
      ),
      _getJsonList(
        '/api/incidents/$incidentId/medical/ics206/air-ambulance',
        query,
      ),
      _getJsonList('/api/incidents/$incidentId/medical/ics206/comms', query),
      _getJson('/api/incidents/$incidentId/medical/ics206/procedures', query),
      _getJson('/api/incidents/$incidentId/medical/ics206/signatures', query),
    ]);

    return Ics206Plan(
      aidStations: Ics206Plan.recordsFromJsonList(results[0] as List<dynamic>),
      ambulanceServices: Ics206Plan.recordsFromJsonList(
        results[1] as List<dynamic>,
      ),
      hospitals: Ics206Plan.recordsFromJsonList(results[2] as List<dynamic>),
      airAmbulance: Ics206Plan.recordsFromJsonList(results[3] as List<dynamic>),
      medicalComms: Ics206Plan.recordsFromJsonList(results[4] as List<dynamic>),
      procedures: Ics206Procedures.fromJson(results[5] as Map<String, dynamic>),
      signatures: Ics206Signatures.fromJson(results[6] as Map<String, dynamic>),
      opPeriod: opPeriod,
    );
  }

  /// Registers (or re-associates) this device's FCM token with the given
  /// person/incident context. The server upserts by `token`, so calling
  /// this repeatedly — including with a different person on the same
  /// device — re-associates rather than duplicating.
  Future<Map<String, dynamic>> registerPushToken({
    required String token,
    String? personRecord,
    String? personId,
    String? incidentId,
    String platform = 'android',
    String? deviceName,
  }) async {
    final response = await _httpClient.post(
      _uri('/api/mobile/push-token'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'token': token,
        'person_record': ?personRecord,
        'person_id': ?personId,
        'incident_id': ?incidentId,
        'platform': platform,
        'device_name': ?deviceName,
      }),
    );
    return _decodeJsonObject(response);
  }

  Future<Map<String, dynamic>> registerClientConnection({
    required String deviceId,
    required String incidentId,
    required String teamId,
    required String teamName,
    required String personRecord,
    String? personId,
    String platform = 'mobile',
    bool locationTrackingEnabled = false,
    String? fcmToken,
  }) async {
    final response = await _httpClient.post(
      _uri('/api/client-connections/register'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'device_id': deviceId,
        'platform': platform,
        'person_record': personRecord,
        'person_id': ?personId,
        'incident_id': incidentId,
        'team_id': teamId,
        'team_name': teamName,
        'location_tracking_enabled': locationTrackingEnabled,
        'fcm_token': ?fcmToken,
      }),
    );
    return _decodeJsonObject(response);
  }

  Future<Map<String, dynamic>> updateClientConnectionPushToken({
    required String deviceId,
    String? fcmToken,
    String? notificationPermission,
  }) async {
    final response = await _httpClient.patch(
      _uri('/api/client-connections/$deviceId/push-token'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'fcm_token': ?fcmToken,
        'notification_permission': ?notificationPermission,
      }),
    );
    return _decodeJsonObject(response);
  }

  Future<Map<String, dynamic>> heartbeatClientConnection({
    required String deviceId,
    bool? locationTrackingEnabled,
  }) async {
    final response = await _httpClient.post(
      _uri('/api/client-connections/$deviceId/heartbeat'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'location_tracking_enabled': ?locationTrackingEnabled}),
    );
    return _decodeJsonObject(response);
  }

  /// Best-effort unregistration (e.g. on logout). Throws SarAppApiException
  /// on a network/HTTP failure — callers must catch/swallow.
  Future<void> unregisterPushToken(String token) async {
    final response = await _httpClient.delete(
      _uri('/api/mobile/push-token/${Uri.encodeComponent(token)}'),
    );
    _decode(response);
  }

  /// Sends one location ping directly to the server, bypassing Tracelet's
  /// own local-storage/sync pipeline entirely (see
  /// [TrackingService.sendManualPing] — a dev/debug tool for testing the
  /// backend independent of Tracelet's background scheduling). Returns the
  /// decoded `{"ok": bool, "recorded": bool}` response. Throws
  /// SarAppApiException on a network/HTTP failure.
  Future<Map<String, dynamic>> sendLocationPing({
    required String connectionToken,
    required double lat,
    required double lon,
    required String teamId,
    String? timestamp,
  }) async {
    final response = await _httpClient.post(
      _uri('/api/mobile/location'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'connection_token': connectionToken,
        'lat': lat,
        'lon': lon,
        'team_id': teamId,
        'timestamp': ?timestamp,
      }),
    );
    return _decodeJsonObject(response);
  }

  /// Tells the server this device stopped location tracking (see
  /// [TrackingService.stop]), so a team's map dot clears immediately instead
  /// of sitting stale at its last reported position. Throws
  /// SarAppApiException on failure — callers must catch/swallow, this must
  /// never block the local stop.
  Future<void> stopMobileLocation(String connectionToken) async {
    final response = await _httpClient.post(
      _uri('/api/mobile/location/stop'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'connection_token': connectionToken}),
    );
    _decode(response);
  }

  void dispose() => _httpClient.close();
}
