import '../utils/json_parsing.dart';

/// Active operational alert computed by the incident overview backend.
/// These are live team-state alerts, not a historical notification feed.
class IncidentAlert {
  const IncidentAlert({
    required this.type,
    required this.teamId,
    required this.teamName,
    required this.status,
    this.lastCheckinAt,
  });

  final String type;
  final String teamId;
  final String teamName;
  final String status;
  final DateTime? lastCheckinAt;

  factory IncidentAlert.fromJson(Map<String, dynamic> json) {
    return IncidentAlert(
      type: '${json['type'] ?? ''}'.trim(),
      teamId: '${json['team_id'] ?? ''}'.trim(),
      teamName: '${json['team_name'] ?? ''}'.trim(),
      status: '${json['status'] ?? ''}'.trim(),
      lastCheckinAt: parseDateTime(json['last_checkin_ts']),
    );
  }

  bool matchesTeam({required String teamId, required String teamName}) {
    final normalizedTeamId = teamId.trim().toLowerCase();
    final normalizedTeamName = teamName.trim().toLowerCase();
    if (normalizedTeamName.isNotEmpty &&
        this.teamName.trim().toLowerCase() == normalizedTeamName) {
      return true;
    }
    if (normalizedTeamId.isNotEmpty &&
        this.teamId.trim().toLowerCase() == normalizedTeamId) {
      return true;
    }
    return false;
  }

  bool get isCritical => type == 'EMERGENCY' || type == 'CHECKIN_OVERDUE';

  String get title {
    switch (type) {
      case 'EMERGENCY':
        return 'Emergency';
      case 'NEEDS_ASSISTANCE':
        return 'Needs Assistance';
      case 'CHECKIN_OVERDUE':
        return 'Check-In Overdue';
      case 'CHECKIN_WARNING':
        return 'Check-In Warning';
      default:
        return type.replaceAll('_', ' ').trim();
    }
  }

  String get body {
    switch (type) {
      case 'EMERGENCY':
        return '$teamName has raised an emergency alert.';
      case 'NEEDS_ASSISTANCE':
        return '$teamName has requested assistance.';
      case 'CHECKIN_OVERDUE':
        return '$teamName has gone too long without a check-in while $status.';
      case 'CHECKIN_WARNING':
        return '$teamName is approaching its required check-in window while $status.';
      default:
        return status.isEmpty
            ? 'Active alert for $teamName.'
            : 'Active alert for $teamName while $status.';
    }
  }
}
