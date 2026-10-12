import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/services/local_profile_store.dart';
import 'package:ics_mobile_app/services/profile_sync.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';

const _profile = LocalProfile(
  personId: '405021',
  firstName: 'Jane',
  lastName: 'Doe',
  organization: 'CAP',
  phone: '555-0100',
);

void main() {
  Future<(List<http.Request>, Object?)> sync(String lookupStatus) async {
    final requests = <http.Request>[];
    final api = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((request) async {
        requests.add(request);
        if (request.url.path == '/api/auth/lookup') {
          return http.Response(
            jsonEncode({'status': lookupStatus, 'person': null}),
            200,
          );
        }
        return http.Response(
          jsonEncode({
            'status': 'found',
            'person': {'name': 'Jane Doe'},
          }),
          200,
        );
      }),
    );
    try {
      await ProfileSync(api).sync(_profile);
      return (requests, null);
    } catch (e) {
      return (requests, e);
    }
  }

  test('an existing record is updated from the device profile', () async {
    final (requests, error) = await sync('found');

    expect(error, isNull);
    final update = requests.singleWhere((r) => r.method == 'PUT');
    expect(update.url.path, '/api/auth/profile');
    final body = jsonDecode(update.body) as Map;
    expect(body['person_id'], '405021');
    expect(body['organization'], 'CAP');
    expect(body['phone'], '555-0100');
    expect(requests.any((r) => r.url.path == '/api/auth/register'), isFalse);
  });

  test('a missing record is created from the device profile', () async {
    final (requests, error) = await sync('not_found');

    expect(error, isNull);
    expect(requests.any((r) => r.url.path == '/api/auth/register'), isTrue);
    expect(requests.any((r) => r.method == 'PUT'), isFalse);
  });

  test('an ambiguous ID writes nothing and reports the problem', () async {
    final (requests, error) = await sync('ambiguous');

    expect(error, isA<SarAppApiException>());
    expect(requests.map((r) => r.method), everyElement('GET'));
  });
}
