import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/services/incident_context_poller.dart';

void main() {
  group('detectTeamTransition', () {
    test('first poll (no prior state) is never a transition', () {
      expect(
        detectTeamTransition(previouslyHadTeam: null, hasTeamNow: true),
        TeamTransition.none,
      );
      expect(
        detectTeamTransition(previouslyHadTeam: null, hasTeamNow: false),
        TeamTransition.none,
      );
    });

    test('no team then a team is gained', () {
      expect(
        detectTeamTransition(previouslyHadTeam: false, hasTeamNow: true),
        TeamTransition.gained,
      );
    });

    test('a team then no team is lost', () {
      expect(
        detectTeamTransition(previouslyHadTeam: true, hasTeamNow: false),
        TeamTransition.lost,
      );
    });

    test('unchanged team state is never a transition', () {
      expect(
        detectTeamTransition(previouslyHadTeam: true, hasTeamNow: true),
        TeamTransition.none,
      );
      expect(
        detectTeamTransition(previouslyHadTeam: false, hasTeamNow: false),
        TeamTransition.none,
      );
    });
  });
}
