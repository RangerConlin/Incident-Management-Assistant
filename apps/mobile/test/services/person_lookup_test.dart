import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/services/local_profile_store.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';

void main() {
  SarAppApiClient clientFor(MockClient mock) =>
      SarAppApiClient(httpClient: mock, baseUrl: 'https://test.local');

  test('lookupPerson returns the matched person name', () async {
    late Uri requested;
    final client = clientFor(MockClient((request) async {
      requested = request.url;
      return http.Response(
        jsonEncode({
          'status': 'found',
          'person': {'name': 'Jane Doe', 'person_record': 42},
        }),
        200,
      );
    }));

    final result = await client.lookupPerson('405021');

    expect(
      requested.toString(),
      'https://test.local/api/auth/lookup?person_id=405021',
    );
    expect(result.status, PersonLookupStatus.found);
    expect(result.name, 'Jane Doe');
  });

  test('lookupPerson maps not_found and ambiguous statuses', () async {
    for (final entry in {
      'not_found': PersonLookupStatus.notFound,
      'ambiguous': PersonLookupStatus.ambiguous,
    }.entries) {
      final client = clientFor(MockClient((_) async => http.Response(
            jsonEncode({'status': entry.key, 'person': null}),
            200,
          )));
      final result = await client.lookupPerson('x');
      expect(result.status, entry.value);
      expect(result.name, isNull);
    }
  });

  test('registerPerson posts the new profile', () async {
    late http.Request captured;
    final client = clientFor(MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode({
          'status': 'found',
          'person': {'name': 'Jane Doe'},
        }),
        201,
      );
    }));

    final result = await client.registerPerson(
      const LocalProfile(
        personId: '405021',
        firstName: 'Jane',
        lastName: 'Doe',
      ),
    );

    expect(captured.url.path, '/api/auth/register');
    final body = jsonDecode(captured.body) as Map;
    expect(body, containsPair('person_id', '405021'));
    expect(body, containsPair('first_name', 'Jane'));
    expect(body, containsPair('last_name', 'Doe'));
    expect(result.name, 'Jane Doe');
  });

  test('error responses surface the server detail message', () async {
    final client = clientFor(MockClient((_) async => http.Response(
          jsonEncode({'detail': 'No personnel record matches this ID.'}),
          404,
        )));

    expect(
      client.startSession(personId: 'nobody', incidentId: 'i1'),
      throwsA(
        isA<SarAppApiException>()
            .having((e) => e.statusCode, 'statusCode', 404)
            .having(
              (e) => e.message,
              'message',
              'No personnel record matches this ID.',
            ),
      ),
    );
  });
}
