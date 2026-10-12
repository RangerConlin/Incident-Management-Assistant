import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/narrative_entry.dart';

void main() {
  group('NarrativeEntry.fromJson', () {
    test('parses critical as an int 0/1 flag into a bool', () {
      final critical = NarrativeEntry.fromJson({
        'id': '1',
        'task_id': 15,
        'timestamp': '2026-07-10T09:42:00Z',
        'narrative': 'Humidity high today.',
        'entered_by': 'Safety Officer',
        'critical': 1,
      });
      final normal = NarrativeEntry.fromJson({
        'id': '2',
        'task_id': 15,
        'timestamp': '2026-07-10T09:47:00Z',
        'narrative': 'Beginning search sweep #2.',
        'entered_by': 'John Smith',
        'critical': 0,
      });

      expect(critical.critical, isTrue);
      expect(normal.critical, isFalse);
    });

    test('parses timestamp into a DateTime', () {
      final entry = NarrativeEntry.fromJson({
        'id': '1',
        'task_id': 15,
        'timestamp': '2026-07-10T09:35:00Z',
        'narrative': 'Assignment created.',
      });
      expect(entry.timestamp, DateTime.parse('2026-07-10T09:35:00Z'));
    });

    test('missing entered_by/team_num degrade gracefully, not with a crash', () {
      final entry = NarrativeEntry.fromJson({
        'id': '1',
        'task_id': 15,
        'timestamp': '2026-07-10T09:35:00Z',
        'narrative': 'Assignment created.',
      });
      expect(entry.enteredBy, '');
      expect(entry.teamNum, isNull);
    });
  });
}
