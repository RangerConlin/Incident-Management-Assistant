class MobileIncidentContext {
  const MobileIncidentContext({
    required this.person,
    required this.resourceStatus,
    required this.staffAssignments,
    this.team,
  });

  final Map<String, dynamic>? person;
  final Map<String, dynamic>? resourceStatus;
  final Map<String, dynamic>? team;
  final List<Map<String, dynamic>> staffAssignments;

  bool get hasTeam => team != null;
  String get teamId => '${team?['team_id'] ?? ''}';
  String get teamName => '${team?['team_name'] ?? ''}';

  factory MobileIncidentContext.fromJson(Map<String, dynamic> json) {
    Map<String, dynamic>? mapOrNull(Object? value) =>
        value is Map ? Map<String, dynamic>.from(value) : null;

    return MobileIncidentContext(
      person: mapOrNull(json['person']),
      resourceStatus: mapOrNull(json['resource_status']),
      team: mapOrNull(json['team']),
      staffAssignments: (json['staff_assignments'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList(),
    );
  }
}
