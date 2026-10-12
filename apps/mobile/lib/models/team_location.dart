import '../utils/json_parsing.dart';

/// Last-known team position returned by
/// `GET /api/incidents/{incident_id}/team-locations`.
class TeamLocation {
  const TeamLocation({
    required this.teamId,
    required this.latitude,
    required this.longitude,
    this.teamName,
    this.updatedAt,
    this.sourcePersonRecord,
    this.sourcePersonId,
    this.localOnly = false,
  });

  final String teamId;
  final String? teamName;
  final double latitude;
  final double longitude;
  final DateTime? updatedAt;

  /// Internal DB key for whoever last posted this location. Never display
  /// this to the user — it means nothing to them. Kept only because
  /// tracking submissions are keyed off it server-side.
  final String? sourcePersonRecord;

  /// The person's actual login id/name, when known. This is what should be
  /// shown in the UI (e.g. the map's team-details "Source" row).
  final String? sourcePersonId;
  final bool localOnly;

  String get displayName => teamName ?? 'Team $teamId';

  factory TeamLocation.fromJson(Map<String, dynamic> json) {
    final lat = _parseDouble(
      json['current_location_lat'] ?? json['lat'] ?? json['latitude'],
    );
    final lon = _parseDouble(
      json['current_location_lon'] ??
          json['lon'] ??
          json['lng'] ??
          json['longitude'],
    );
    if (lat == null || lon == null) {
      throw const FormatException('Team location is missing coordinates');
    }

    final teamId =
        json['team_id'] ?? json['int_id'] ?? json['id'] ?? json['_id'] ?? '';

    return TeamLocation(
      teamId: '$teamId',
      teamName: nullIfBlank(json['team_name'] ?? json['name']),
      latitude: lat,
      longitude: lon,
      updatedAt: parseDateTime(
        json['current_location_updated_at'] ??
            json['updated_at'] ??
            json['timestamp'],
      ),
      sourcePersonRecord: nullIfBlank(
        json['current_location_person_record'] ?? json['person_record'],
      ),
      sourcePersonId: nullIfBlank(
        json['current_location_person_id'] ??
            json['current_location_username'] ??
            json['person_id'] ??
            json['username'],
      ),
    );
  }

  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    return double.tryParse('$value');
  }
}
