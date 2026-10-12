import '../utils/json_parsing.dart';

/// A single task narrative log entry (`GET/POST .../incidents/{id}/narratives`).
///
/// The backend document has no category/entry-type field today — only a
/// `critical` flag — so any category shown in the UI is a client-side
/// presentation heuristic, not stored data (see `narrative_category.dart`).
class NarrativeEntry {
  const NarrativeEntry({
    required this.id,
    required this.taskId,
    required this.timestamp,
    required this.narrative,
    required this.enteredBy,
    this.teamNum,
    this.critical = false,
  });

  final String id;
  final int taskId;
  final DateTime timestamp;
  final String narrative;
  final String enteredBy;
  final String? teamNum;
  final bool critical;

  factory NarrativeEntry.fromJson(Map<String, dynamic> json) {
    return NarrativeEntry(
      id: '${json['id'] ?? json['_id'] ?? ''}',
      taskId: parseInt(json['task_id']) ?? -1,
      timestamp: parseDateTime(json['timestamp']) ?? DateTime.fromMillisecondsSinceEpoch(0),
      narrative: '${json['narrative'] ?? ''}',
      enteredBy: '${json['entered_by'] ?? ''}',
      teamNum: nullIfBlank(json['team_num']),
      critical: parseIntBool(json['critical']),
    );
  }
}
