import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/screens/profile_qr_review_screen.dart';
import 'package:ics_mobile_app/services/local_profile_store.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';
import 'package:ics_mobile_app/utils/check_in_qr.dart';

void main() {
  testWidgets('reviews every profile section and applies approved check-in', (
    tester,
  ) async {
    final requests = <http.Request>[];
    final api = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((request) async {
        requests.add(request);
        if (request.url.path.endsWith('/preview')) {
          return http.Response(
            jsonEncode({
              'match_status': 'new',
              'profile': {},
              'differences': [],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response(
          jsonEncode({'person_record': 42, 'status': 'Checked In'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );
    const profile = LocalProfile(
      personId: 'CAP-42',
      firstName: 'Casey',
      lastName: 'Responder',
      emergencyInfo: {'primary_name': 'Morgan Responder'},
      contactInfo: {'city': 'Exampleville'},
      certifications: [
        {'cert_type_id': 2003, 'level': 2},
      ],
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ProfileQrReviewScreen(
          incidentId: 'INC-1',
          payload: CheckInQr.payload(profile),
          teamId: 7,
          approvedByPersonRecord: 99,
          apiClient: api,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Casey Responder'), findsWidgets);
    await tester.scrollUntilVisible(
      find.textContaining('Morgan Responder'),
      250,
    );
    expect(find.textContaining('Morgan Responder'), findsOneWidget);
    await tester.scrollUntilVisible(find.textContaining('Exampleville'), 250);
    expect(find.textContaining('Exampleville'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.textContaining('cert type id: 2003'),
      250,
    );
    expect(find.textContaining('cert type id: 2003'), findsOneWidget);

    await tester.ensureVisible(find.text('Approve, check in, and add to team'));
    await tester.tap(find.text('Approve, check in, and add to team'));
    await tester.pumpAndSettle();

    expect(requests, hasLength(2));
    final body = jsonDecode(requests.last.body) as Map<String, dynamic>;
    expect(body['team_id'], 7);
    expect(body['approved_by_person_record'], 99);
    expect((body['profile'] as Map<String, dynamic>)['person_id'], 'CAP-42');
  });
}
