import '../utils/json_parsing.dart';

/// A field task assigned to one or more teams for the current incident.
class Task {
  const Task({
    required this.id,
    required this.intId,
    required this.taskNumber,
    required this.title,
    required this.status,
    required this.priority,
    this.category,
    this.taskType,
    this.location,
    this.taskTeams = const [],
    this.activeTeamIds = const [],
  });

  final String id;
  final int? intId;
  final String taskNumber;
  final String title;
  final String status;
  final int priority;
  final String? category;
  final String? taskType;
  final String? location;
  final List<TaskTeamAssignment> taskTeams;
  final List<int> activeTeamIds;

  static const Map<int, String> priorityMap = {
    1: 'Low',
    2: 'Medium',
    3: 'High',
    4: 'Critical',
  };

  String get priorityLabel => priorityMap[priority] ?? 'Unknown';

  String get typeLabel => taskType ?? category ?? '—';

  TaskTeamAssignment? assignmentFor(int? teamIntId) {
    if (teamIntId == null) return null;
    for (final assignment in taskTeams) {
      if (assignment.teamId == teamIntId) return assignment;
    }
    return null;
  }

  factory Task.fromJson(Map<String, dynamic> json) {
    return Task(
      id: '${json['id'] ?? json['_id'] ?? ''}',
      intId: parseInt(json['int_id']),
      taskNumber: '${json['task_id'] ?? json['int_id'] ?? json['id'] ?? '—'}',
      title: '${json['title'] ?? ''}',
      status: '${json['status'] ?? ''}',
      priority: parseInt(json['priority']) ?? 0,
      category: nullIfBlank(json['category']),
      taskType: nullIfBlank(json['task_type']),
      location: nullIfBlank(json['location']),
      taskTeams: ((json['task_teams'] as List?) ?? const [])
          .whereType<Map>()
          .map((e) => TaskTeamAssignment.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      activeTeamIds: ((json['active_team_ids'] as List?) ?? const [])
          .map(parseInt)
          .whereType<int>()
          .toList(),
    );
  }
}

class TaskTeamAssignment {
  const TaskTeamAssignment({
    required this.teamId,
    this.teamName,
    this.sortieId,
    this.timeAssigned,
    this.timeBriefed,
    this.timeEnroute,
    this.timeArrived,
    this.timeDiscovery,
    this.timeComplete,
    this.timeCleared,
  });

  final int teamId;
  final String? teamName;
  final String? sortieId;
  final DateTime? timeAssigned;
  final DateTime? timeBriefed;
  final DateTime? timeEnroute;
  final DateTime? timeArrived;
  final DateTime? timeDiscovery;
  final DateTime? timeComplete;
  final DateTime? timeCleared;

  factory TaskTeamAssignment.fromJson(Map<String, dynamic> json) {
    return TaskTeamAssignment(
      teamId: parseInt(json['team_id']) ?? -1,
      teamName: nullIfBlank(json['team_name']),
      sortieId: json['sortie_id']?.toString(),
      timeAssigned: parseDateTime(json['time_assigned']),
      timeBriefed: parseDateTime(json['time_briefed']),
      timeEnroute: parseDateTime(json['time_enroute']),
      timeArrived: parseDateTime(json['time_arrived']),
      timeDiscovery: parseDateTime(json['time_discovery']),
      timeComplete: parseDateTime(json['time_complete']),
      timeCleared: parseDateTime(json['time_cleared']),
    );
  }
}
