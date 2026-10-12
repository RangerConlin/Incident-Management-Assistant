import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/services/incident_session_starter.dart';
import 'package:ics_mobile_app/services/local_profile_store.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';
import 'package:ics_mobile_app/services/session_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _profile = LocalProfile(
  personId: '405021',
  firstName: 'Jane',
  lastName: 'Doe',
  organization: 'CAP',
  radioId: 'R-7',
);

typedef _Outcome = ({
  StartedIncident? started,
  List<http.Request> requests,
  Object? error,
});

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  Future<_Outcome> run(String lookupStatus) async {
    final requests = <http.Request>[];
    final api = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((request) async {
        requests.add(request);
        switch (request.url.path) {
          case '/api/auth/lookup':
            return http.Response(
              jsonEncode({'status': lookupStatus, 'person': null}),
              200,
            );
          case '/api/auth/register':
            return http.Response(
              jsonEncode({
                'status': 'found',
                'person': {'name': 'Jane Doe'},
              }),
              201,
            );
          case '/api/auth/sessions':
            return http.Response(
              jsonEncode({'session_id': 's1', 'person_record': 42}),
              201,
            );
          case '/api/incidents/i1/profile':
            return http.Response(jsonEncode({'type': 'SAR'}), 200);
          default:
            return http.Response('{}', 200);
        }
      }),
    );
    try {
      final started = await IncidentSessionStarter(api).start(
        profile: _profile,
        incidentId: 'i1',
        incidentName: 'Training',
        teamId: 't1',
        teamName: 'Team 1',
      );
      return (started: started, requests: requests, error: null);
    } catch (e) {
      return (started: null, requests: requests, error: e);
    }
  }

  test('a profile the server already knows just starts the session', () async {
    final outcome = await run('found');

    expect(outcome.error, isNull);
    expect(
      outcome.requests.any((r) => r.url.path == '/api/auth/register'),
      isFalse,
    );
    expect(outcome.started?.session['person_id'], '405021');
    expect(outcome.started?.incidentType, 'SAR');
    final saved = await SessionStore.load();
    expect(saved?.incidentId, 'i1');
    expect(saved?.teamName, 'Team 1');
  });

  test('an unknown profile is registered with all its fields first', () async {
    final outcome = await run('not_found');

    expect(outcome.error, isNull);
    expect(outcome.started, isNotNull);
    final paths = outcome.requests.map((r) => r.url.path).toList();
    expect(
      paths.indexOf('/api/auth/register') < paths.indexOf('/api/auth/sessions'),
      isTrue,
    );
    final body =
        jsonDecode(
              outcome.requests
                  .singleWhere((r) => r.url.path == '/api/auth/register')
                  .body,
            )
            as Map;
    expect(body['first_name'], 'Jane');
    expect(body['organization'], 'CAP');
    expect(body['radio_id'], 'R-7');
  });

  test('an ambiguous ID stops before any session is started', () async {
    final outcome = await run('ambiguous');

    expect(outcome.started, isNull);
    expect(outcome.error, isA<SarAppApiException>());
    expect(
      outcome.requests.any((r) => r.url.path == '/api/auth/sessions'),
      isFalse,
    );
    expect(await SessionStore.load(), isNull);
  });
}
