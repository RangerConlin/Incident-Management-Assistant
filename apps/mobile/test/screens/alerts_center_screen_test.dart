import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/models/home_nav_args.dart';
import 'package:ics_mobile_app/screens/alerts_center_screen.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';

const _incidentId = 'INC1';

HomeNavArgs _args({String teamId = '4', String teamName = 'GT-4 Alpha'}) =>
    HomeNavArgs(
      incidentId: _incidentId,
      incidentName: 'Missing Aircraft Search',
      teamId: teamId,
      teamName: teamName,
      session: const {'person_id': 'P100'},
      incidentType: 'Missing Person',
    );

SarAppApiClient _client({
  required List<Map<String, dynamic>> alerts,
  int statusCode = 200,
}) {
  final mock = MockClient((request) async {
    if (request.method == 'GET' &&
        request.url.path == '/api/incidents/$_incidentId/alerts') {
      return http.Response(jsonEncode(alerts), statusCode);
    }
    return http.Response('not found', 404);
  });
  return SarAppApiClient(httpClient: mock, baseUrl: 'https://test.local');
}

Widget _wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('alerts screen only shows alerts for the signed-in team', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        AlertsCenterScreen(
          args: _args(),
          apiClient: _client(
            alerts: const [
              {
                'type': 'CHECKIN_OVERDUE',
                'team_id': 9,
                'team_name': 'GT-9 Charlie',
                'status': 'Enroute',
                'last_checkin_ts': '2026-07-18T10:30:00Z',
              },
              {
                'type': 'NEEDS_ASSISTANCE',
                'team_id': 4,
                'team_name': 'GT-4 Alpha',
                'status': 'On Scene',
                'last_checkin_ts': '2026-07-18T11:15:00Z',
              },
            ],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Needs Assistance'), findsOneWidget);
    expect(find.textContaining('GT-4 Alpha'), findsOneWidget);
    expect(find.text('Check-In Overdue'), findsNothing);
    expect(find.textContaining('GT-9 Charlie'), findsNothing);
  });

  testWidgets('empty team-specific result shows an honest empty state', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        AlertsCenterScreen(
          args: _args(),
          apiClient: _client(
            alerts: const [
              {
                'type': 'EMERGENCY',
                'team_id': 7,
                'team_name': 'GT-7 Bravo',
                'status': 'Available',
              },
            ],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No active alerts for your team.'), findsOneWidget);
    expect(find.textContaining('GT-7 Bravo'), findsNothing);
  });

  testWidgets('server failure shows retryable error state', (tester) async {
    await tester.pumpWidget(
      _wrap(
        AlertsCenterScreen(
          args: _args(),
          apiClient: _client(alerts: const [], statusCode: 500),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Unable to load alerts.'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });
}
