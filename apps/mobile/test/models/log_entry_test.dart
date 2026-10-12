import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/log_entry.dart';

void main() {
  test('parses a server entry and splits activity from note', () {
    final entry = LogEntry.fromJson({
      'id': 'e1',
      'timestamp_utc': '2026-09-19T14:30:00+00:00',
      'text': 'Departed staging\nTwo members, full kit',
      'actor_user_id': 'P100',
      'source': 'mobile',
      'critical_flag': true,
    });

    expect(entry.id, 'e1');
    expect(entry.activity, 'Departed staging');
    expect(entry.note, 'Two members, full kit');
    expect(entry.actorUserId, 'P100');
    expect(entry.critical, isTrue);
    expect(entry.timestamp.toUtc().hour, 14);
  });

  test('single-line text has no note', () {
    final entry = LogEntry.fromJson({'id': 'e2', 'text': 'Arrived at LKP'});
    expect(entry.activity, 'Arrived at LKP');
    expect(entry.note, isNull);
  });

  test('composeText round-trips through activity and note', () {
    final text = LogEntry.composeText('Found clue', 'Red jacket');
    final entry = LogEntry.fromJson({'text': text});
    expect(entry.activity, 'Found clue');
    expect(entry.note, 'Red jacket');
    expect(LogEntry.composeText('Found clue', null), 'Found clue');
    expect(LogEntry.composeText('Found clue', ''), 'Found clue');
  });
}
