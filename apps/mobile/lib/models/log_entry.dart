import '../utils/json_parsing.dart';

/// A single ICS 214 activity-log entry on a team's stream
/// (`GET/POST .../incidents/{id}/mobile/teams/{team_id}/log`).
///
/// The server stores one free-text `text` field per entry, so the sheet's
/// activity and optional note are joined by a newline on write and split
/// back apart for display.
class LogEntry {
  const LogEntry({
    required this.id,
    required this.timestamp,
    required this.text,
    this.actorUserId,
    this.source = '',
    this.critical = false,
  });

  final String id;
  final DateTime timestamp;
  final String text;
  final String? actorUserId;

  /// `mobile`, `manual` (desktop), or `auto` (system-generated).
  final String source;
  final bool critical;

  /// First line of [text].
  String get activity => text.split('\n').first;

  /// Everything after the first line, or null when there is none.
  String? get note {
    final index = text.indexOf('\n');
    if (index < 0) return null;
    final rest = text.substring(index + 1).trim();
    return rest.isEmpty ? null : rest;
  }

  /// Text as sent to the server for an [activity] and optional [note].
  static String composeText(String activity, String? note) =>
      note == null || note.isEmpty ? activity : '$activity\n$note';

  factory LogEntry.fromJson(Map<String, dynamic> json) {
    return LogEntry(
      id: '${json['id'] ?? ''}',
      timestamp:
          parseDateTime(json['timestamp_utc']) ??
          DateTime.fromMillisecondsSinceEpoch(0),
      text: '${json['text'] ?? ''}',
      actorUserId: nullIfBlank(json['actor_user_id']),
      source: '${json['source'] ?? ''}',
      critical: parseIntBool(json['critical_flag']),
    );
  }
}
