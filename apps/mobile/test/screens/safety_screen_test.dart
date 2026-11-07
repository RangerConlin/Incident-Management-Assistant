import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/models/home_nav_args.dart';
import 'package:ics_mobile_app/screens/report_hazard_screen.dart';
import 'package:ics_mobile_app/screens/safety_screen.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';

const _args = HomeNavArgs(
  incidentId: 'INC-1',
  incidentName: 'Search',
  teamId: '4',
  teamName: 'Team 4',
  session: {'person_id': 'P-7'},
);

SarAppApiClient _client(Future<http.Response> Function(http.Request) handler) =>
    SarAppApiClient(
      httpClient: MockClient(handler),
      baseUrl: 'https://test.local',
    );

void main() {
  testWidgets('loads hazards and field reports from the incident API', (
    tester,
  ) async {
    final client = _client((request) async {
      if (request.url.path.endsWith('/safety/hazards')) {
        return http.Response(
          jsonEncode([
            {
              'title': 'Loose rock',
              'location_text': 'North ridge',
              'spe_residual': {'band': 'Possible'},
            },
          ]),
          200,
        );
      }
      if (request.url.path.endsWith('/safety/reports')) {
        return http.Response(
          jsonEncode([
            {
              'notes': 'Vehicle blocking egress',
              'severity': 'High',
              'flagged': true,
              'time': '2026-11-07T12:00:00Z',
            },
          ]),
          200,
        );
      }
      return http.Response('not found', 404);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: SafetyScreen(args: _args, apiClient: client),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Loose rock'), findsOneWidget);
    expect(find.text('North ridge · Possible'), findsOneWidget);
    expect(find.text('Vehicle blocking egress'), findsOneWidget);
    expect(find.text('Scaffold only'), findsNothing);
  });

  testWidgets('submits a real field safety report', (tester) async {
    Map<String, dynamic>? posted;
    final client = _client((request) async {
      if (request.method == 'POST' &&
          request.url.path.endsWith('/safety/reports')) {
        posted = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(jsonEncode({'id': 1}), 201);
      }
      return http.Response('not found', 404);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: ReportHazardScreen(args: _args, apiClient: client),
      ),
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Safety concern or hazard'),
      'Downed power line',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Location'),
      'Sector B',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Submit Report'));
    await tester.pumpAndSettle();

    expect(posted?['notes'], 'Downed power line');
    expect(posted?['location'], 'Sector B');
    expect(posted?['reported_by'], 'P-7');
    expect(posted?['team_id'], 4);
  });
}
