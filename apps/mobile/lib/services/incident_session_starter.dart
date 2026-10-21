import 'local_profile_store.dart';
import 'profile_sync.dart';
import 'sarapp_api_client.dart';
import 'session_store.dart';

/// Everything the dashboard needs once an incident has been joined.
class StartedIncident {
  const StartedIncident({
    required this.incidentId,
    required this.incidentName,
    required this.incidentType,
    required this.teamId,
    required this.teamName,
    required this.session,
  });

  final String incidentId;
  final String incidentName;
  final String? incidentType;
  final String teamId;
  final String teamName;
  final Map<String, dynamic> session;
}

/// Joins an incident as the on-device profile: brings the connected server's
/// personnel record in line with it (creating one if needed), starts the
/// server session, associates the chosen team, and saves the session locally
/// so the app reopens straight into the incident.
class IncidentSessionStarter {
  IncidentSessionStarter(this._api);

  final SarAppApiClient _api;

  Future<StartedIncident> start({
    required LocalProfile profile,
    required String incidentId,
    required String incidentName,
    String? teamId,
    String? teamName,
  }) async {
    await ProfileSync(_api).sync(profile);

    final session = await _api.startSession(
      personId: profile.personId,
      incidentId: incidentId,
    );

    // The server's session response echoes an internal person_record under
    // some of the same-looking keys in practice; never trust it for display.
    // The profile's person id is authoritative — pin it so every downstream
    // screen shows the real id, not the record.
    session['person_id'] = profile.personId;

    final personRecord =
        session['person_record'] ?? session['user']?['person_record'];
    if (personRecord == null) {
      throw SarAppApiException(
        'The server session did not identify a personnel record.',
      );
    }
    final context = await _api.enterIncident(
      incidentId: incidentId,
      personRecord: int.parse('$personRecord'),
      teamId: teamId,
    );
    session['mobile_context'] = {
      'person': context.person,
      'resource_status': context.resourceStatus,
      'team': context.team,
      'staff_assignments': context.staffAssignments,
    };
    final resolvedTeamId = context.teamId;
    final resolvedTeamName = context.teamName;

    // Best-effort: the incident type drives which tab content/extra screens
    // show up (see `IncidentCategory`). An unknown type falls back to the
    // most feature-complete category.
    String? incidentType;
    try {
      final incidentProfile = await _api.fetchIncidentProfile(incidentId);
      final type = '${incidentProfile['type'] ?? ''}'.trim();
      incidentType = type.isEmpty ? null : type;
    } on SarAppApiException {
      incidentType = null;
    }

    await SessionStore.save(
      incidentId: incidentId,
      incidentName: incidentName,
      incidentType: incidentType,
      teamId: resolvedTeamId,
      teamName: resolvedTeamName,
      session: session,
    );

    // Location tracking is never auto-started here — it's an explicit opt-in
    // via the Settings toggle (see TrackingService.start / resumeIfEnabled).

    return StartedIncident(
      incidentId: incidentId,
      incidentName: incidentName,
      incidentType: incidentType,
      teamId: resolvedTeamId,
      teamName: resolvedTeamName,
      session: session,
    );
  }
}
