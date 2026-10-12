import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/task.dart';

void main() {
  group('Task.fromJson', () {
    test('parses a full task document', () {
      final task = Task.fromJson({
        'id': 'abc123',
        'int_id': 15,
        'task_id': 'T-15',
        'title': 'Grid Search Charlie-7',
        'category': 'Ground SAR',
        'task_type': 'Grid Search',
        'priority': 3,
        'status': 'Assigned',
        'location': 'Charlie-7 Grid / Access via Forest Road 212',
        'task_teams': [
          {
            'team_id': 4,
            'team_name': 'GT-4 Alpha',
            'time_assigned': '2026-07-10T09:35:00Z',
          },
        ],
        'active_team_ids': [4],
      });

      expect(task.intId, 15);
      expect(task.taskNumber, 'T-15');
      expect(task.title, 'Grid Search Charlie-7');
      expect(task.typeLabel, 'Grid Search');
      expect(task.priorityLabel, 'High');
      expect(task.status, 'Assigned');
      expect(task.location, 'Charlie-7 Grid / Access via Forest Road 212');
      expect(task.activeTeamIds, [4]);
      expect(task.assignmentFor(4)?.teamName, 'GT-4 Alpha');
      expect(task.assignmentFor(4)?.timeAssigned, DateTime.parse('2026-07-10T09:35:00Z'));
      expect(task.assignmentFor(99), isNull);
    });

    test('handles missing location as null, not an empty string', () {
      final task = Task.fromJson({
        'int_id': 1,
        'title': 'Task with no location',
        'priority': 1,
        'status': 'Draft',
      });
      expect(task.location, isNull);
    });

    test('handles blank-string location as null', () {
      final task = Task.fromJson({'int_id': 1, 'priority': 1, 'status': 'Draft', 'location': '   '});
      expect(task.location, isNull);
    });

    test('falls back to category when task_type is absent', () {
      final task = Task.fromJson({
        'int_id': 1,
        'priority': 1,
        'status': 'Draft',
        'category': 'Ground SAR',
      });
      expect(task.typeLabel, 'Ground SAR');
    });

    test('unknown priority value produces a safe fallback label', () {
      final task = Task.fromJson({'int_id': 1, 'priority': 99, 'status': 'Draft'});
      expect(task.priorityLabel, 'Unknown');
    });

    test('priority arriving as a numeric string is still parsed', () {
      final task = Task.fromJson({'int_id': 1, 'priority': '2', 'status': 'Draft'});
      expect(task.priorityLabel, 'Medium');
    });
  });
}
