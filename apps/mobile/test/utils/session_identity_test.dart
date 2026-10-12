import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/utils/session_identity.dart';

void main() {
  group('SessionIdentity', () {
    test('uses the server-computed person_fullname', () {
      final session = <String, dynamic>{
        'person_id': '405021',
        'person_fullname': 'Jane Doe',
      };
      expect(SessionIdentity.personId(session), '405021');
      expect(SessionIdentity.operatorName(session), 'Jane Doe');
      expect(SessionIdentity.displayName(session), 'Jane Doe');
    });

    test('a session without person_fullname has no operator name', () {
      expect(SessionIdentity.operatorName({'person_id': '405021'}), isNull);
      expect(
        SessionIdentity.operatorName({'person_id': '405021', 'person_fullname': ' '}),
        isNull,
      );
    });

    test('falls back to the id, then the supplied fallback', () {
      expect(
        SessionIdentity.displayName({'person_id': '405021'}),
        '405021',
      );
      expect(
        SessionIdentity.displayName(const {}, fallback: 'Mobile Team Menu'),
        'Mobile Team Menu',
      );
    });
  });
}
