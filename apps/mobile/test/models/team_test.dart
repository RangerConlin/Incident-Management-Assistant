import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/team.dart';

void main() {
  group('Team.fromJson', () {
    test('parses a team with an active task', () {
      final team = Team.fromJson({
        'int_id': 4,
        'name': 'GT-4 Alpha',
        'status': 'Searching',
        'status_updated': '2026-07-10T09:41:00Z',
        'current_task_id': 15,
        'leader_name': 'John Smith',
        'team_type': 'gt',
      });

      expect(team.intId, 4);
      expect(team.name, 'GT-4 Alpha');
      expect(team.status, 'Searching');
      expect(team.currentTaskId, 15);
      expect(team.leaderName, 'John Smith');
      expect(team.teamType, 'GT');
    });

    test('missing current_task_id parses as null (no active task)', () {
      final team = Team.fromJson({'int_id': 4, 'name': 'GT-4 Alpha', 'status': 'Available'});
      expect(team.currentTaskId, isNull);
    });

    test('missing status defaults to Unknown rather than an empty string', () {
      final team = Team.fromJson({'int_id': 4, 'name': 'GT-4 Alpha'});
      expect(team.status, 'Unknown');
    });
  });
}
