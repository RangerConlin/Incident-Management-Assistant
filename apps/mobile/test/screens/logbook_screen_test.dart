import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/models/home_nav_args.dart';
import 'package:ics_mobile_app/screens/logbook_screen.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';

const _logPath = '/api/incidents/INC1/mobile/teams/4/log';

HomeNavArgs _args({String teamId = '4'}) => HomeNavArgs(
      incidentId: 'INC1',
      incidentName: 'Missing Aircraft Search',
      teamId: teamId,
      teamName: 'GT-4 Alpha',
      session: const {'person_id': 'P100'},
    );

Widget _wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('loads the team log newest first', (tester) async {
    final client = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((request) async {
        expect(request.url.path, _logPath);
        return http.Response(
          jsonEncode([
            {'id': 'a', 'timestamp_utc': '2026-09-19T10:00:00+00:00', 'text': 'Older'},
            {'id': 'b', 'timestamp_utc': '2026-09-19T11:00:00+00:00', 'text': 'Newer\nDetail'},
          ]),
          200,
        );
      }),
    );
    await tester.pumpWidget(_wrap(LogbookScreen(args: _args(), apiClient: client)));
    await tester.pumpAndSettle();

    expect(find.text('Detail'), findsOneWidget);
    expect(
      tester.getTopLeft(find.text('Newer')).dy,
      lessThan(tester.getTopLeft(find.text('Older')).dy),
    );
  });

  testWidgets('empty log shows an honest empty state', (tester) async {
    final client = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((_) async => http.Response('[]', 200)),
    );
    await tester.pumpWidget(_wrap(LogbookScreen(args: _args(), apiClient: client)));
    await tester.pumpAndSettle();

    expect(find.text('No log entries yet.'), findsOneWidget);
  });

  testWidgets('server failure shows a retryable error', (tester) async {
    final client = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((_) async => http.Response('boom', 500)),
    );
    await tester.pumpWidget(_wrap(LogbookScreen(args: _args(), apiClient: client)));
    await tester.pumpAndSettle();

    expect(find.text('Unable to load the logbook.'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });

  testWidgets('adding an entry posts to the team log and reloads', (tester) async {
    final entries = <Map<String, dynamic>>[];
    Map<String, dynamic>? posted;
    final client = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((request) async {
        expect(request.url.path, _logPath);
        if (request.method == 'POST') {
          posted = jsonDecode(request.body) as Map<String, dynamic>;
          entries.add({
            'id': 'n1',
            'timestamp_utc': posted!['timestamp_utc'],
            'text': posted!['text'],
          });
          return http.Response(jsonEncode(entries.last), 201);
        }
        return http.Response(jsonEncode(entries), 200);
      }),
    );
    await tester.pumpWidget(_wrap(LogbookScreen(args: _args(), apiClient: client)));
    await tester.pumpAndSettle();

    await tester.tap(find.byType(FloatingActionButton));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Activity'), 'Departed staging');
    await tester.tap(find.text('Add Entry'));
    await tester.pumpAndSettle();

    expect(posted!['text'], 'Departed staging');
    expect(posted!['actor_user_id'], 'P100');
    expect(find.text('Departed staging'), findsOneWidget);
  });
}
