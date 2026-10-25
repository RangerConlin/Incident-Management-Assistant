import '../utils/json_parsing.dart';

/// A field team's current operational state, as tracked by the desktop
/// app's operations module (`GET/PATCH .../operations/teams/{team_id}`,
/// keyed by the team's `int_id` — see the field-dashboard plan for why this
/// differs from the check-in module's own `team_id` field).
class Team {
  const Team({
    required this.intId,
    required this.name,
    required this.status,
    this.statusUpdated,
    this.currentTaskId,
    this.leaderName,
    this.leaderPhone,
    this.teamType,
  });

  final int intId;
  final String name;
  final String status;
  final DateTime? statusUpdated;
  final int? currentTaskId;
  final String? leaderName;
  final String? leaderPhone;
  final String? teamType;

  factory Team.fromJson(Map<String, dynamic> json) {
    return Team(
      intId: parseInt(json['int_id']) ?? -1,
      name: '${json['name'] ?? ''}',
      status: '${json['status'] ?? 'Unknown'}',
      statusUpdated: parseDateTime(json['status_updated']),
      currentTaskId: parseInt(json['current_task_id']),
      leaderName: nullIfBlank(json['leader_name']),
      leaderPhone: nullIfBlank(json['leader_phone']),
      teamType: nullIfBlank(json['team_type'])?.toUpperCase(),
    );
  }
}
