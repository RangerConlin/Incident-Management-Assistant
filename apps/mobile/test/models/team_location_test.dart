import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/team_location.dart';

void main() {
  group('TeamLocation.fromJson', () {
    test('parses current location fields from the team-locations endpoint', () {
      final location = TeamLocation.fromJson({
        'team_id': 4,
        'team_name': 'GT-4 Alpha',
        'current_location_lat': '38.8951',
        'current_location_lon': -106.7621,
        'current_location_updated_at': '2026-07-14T12:34:56Z',
        'current_location_person_record': 'person-1',
      });

      expect(location.teamId, '4');
      expect(location.displayName, 'GT-4 Alpha');
      expect(location.latitude, 38.8951);
      expect(location.longitude, -106.7621);
      expect(location.updatedAt, DateTime.parse('2026-07-14T12:34:56Z'));
      expect(location.sourcePersonRecord, 'person-1');
    });

    test('rejects rows without usable coordinates', () {
      expect(
        () => TeamLocation.fromJson({'team_id': 4}),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
