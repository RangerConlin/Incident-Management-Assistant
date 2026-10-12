/// Bundled navigation context passed between the primary tab screens and
/// drawer routes so each can be constructed consistently.
class HomeNavArgs {
  const HomeNavArgs({
    required this.incidentId,
    required this.incidentName,
    required this.teamId,
    required this.teamName,
    required this.session,
    this.incidentType,
  });

  final String incidentId;
  final String incidentName;
  final String teamId;
  final String teamName;
  final Map<String, dynamic> session;

  /// The incident's free-text type (e.g. "Missing Person", "Wildfire
  /// Response"), from `GET /api/incidents/{id}/profile`. Null if it
  /// couldn't be fetched — category resolution treats that the same as an
  /// unrecognized type (see `categoryForIncidentType`).
  final String? incidentType;
}
