import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/models/home_nav_args.dart';
import 'package:ics_mobile_app/screens/logbook_screen.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';

const _logPath = '/api/incidents/INC1/ics214/entries';

HomeNavArgs _args({String teamId = '4'}) => HomeNavArgs(
  incidentId: 'INC1',
  incidentName: 'Missing Aircraft Search',
  teamId: teamId,
  teamName: 'GT-4 Alpha',
  session: const {'person_id': 'P100', 'person_record': 100},
);

Widget _wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('defaults to the personal log and loads it newest first', (
    tester,
  ) async {
    final client = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((request) async {
        expect(request.url.path, _logPath);
        expect(request.url.queryParameters['person_id'], '100');
        return http.Response(
          jsonEncode([
            {
              'id': 'a',
              'occurred_at': '2026-09-19T10:00:00+00:00',
              'text': 'Older',
            },
            {
              'id': 'b',
              'occurred_at': '2026-09-19T11:00:00+00:00',
              'text': 'Newer\nDetail',
            },
          ]),
          200,
        );
      }),
    );
    await tester.pumpWidget(
      _wrap(LogbookScreen(args: _args(), apiClient: client)),
    );
    await tester.pumpAndSettle();

    expect(find.text('Detail'), findsOneWidget);
    expect(find.text('Personal'), findsOneWidget);
    expect(
      tester.getTopLeft(find.text('Newer')).dy,
      lessThan(tester.getTopLeft(find.text('Older')).dy),
    );
  });

  testWidgets('switches between personal, team, and incident streams', (
    tester,
  ) async {
    final queries = <Map<String, String>>[];
    final client = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((request) async {
        queries.add(request.url.queryParameters);
        return http.Response('[]', 200);
      }),
    );
    await tester.pumpWidget(
      _wrap(LogbookScreen(args: _args(), apiClient: client)),
    );
    await tester.pumpAndSettle();

    expect(queries.last, {'person_id': '100'});

    await tester.tap(find.text('Team'));
    await tester.pumpAndSettle();
    expect(queries.last, {'team_id': '4'});

    await tester.tap(find.text('Incident'));
    await tester.pumpAndSettle();
    expect(queries.last, isEmpty);
  });

  testWidgets('empty log shows an honest empty state', (tester) async {
    final client = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((_) async => http.Response('[]', 200)),
    );
    await tester.pumpWidget(
      _wrap(LogbookScreen(args: _args(), apiClient: client)),
    );
    await tester.pumpAndSettle();

    expect(find.text('No personal log entries yet.'), findsOneWidget);
  });

  testWidgets('server failure shows a retryable error', (tester) async {
    final client = SarAppApiClient(
      baseUrl: 'https://test.local',
      httpClient: MockClient((_) async => http.Response('boom', 500)),
    );
    await tester.pumpWidget(
      _wrap(LogbookScreen(args: _args(), apiClient: client)),
    );
    await tester.pumpAndSettle();

    expect(find.text('Unable to load the logbook.'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });

  testWidgets(
    'adding an entry posts to the selected personal log and reloads',
    (tester) async {
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
              'occurred_at': posted!['occurred_at'],
              'text': posted!['text'],
            });
            return http.Response(jsonEncode(entries.last), 201);
          }
          return http.Response(jsonEncode(entries), 200);
        }),
      );
      await tester.pumpWidget(
        _wrap(LogbookScreen(args: _args(), apiClient: client)),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byType(FloatingActionButton));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Activity'),
        'Departed staging',
      );
      await tester.tap(find.text('Add Entry'));
      await tester.pumpAndSettle();

      expect(posted!['text'], 'Departed staging');
      expect(posted!['created_by'], 'P100');
      expect(posted!['person_ids'], [100]);
      expect(posted!['team_ids'], isEmpty);
      expect(posted!['incident_wide'], false);
      expect(find.text('Departed staging'), findsOneWidget);
    },
  );
}
