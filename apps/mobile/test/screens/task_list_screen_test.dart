import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/models/home_nav_args.dart';
import 'package:ics_mobile_app/screens/task_list_screen.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';

const _incidentId = 'INC1';

HomeNavArgs _args({String teamId = '4'}) => HomeNavArgs(
      incidentId: _incidentId,
      incidentName: 'Missing Aircraft Search',
      teamId: teamId,
      teamName: 'GT-4 Alpha',
      session: const {'person_id': 'P100'},
      incidentType: 'Missing Person',
    );

List<Map<String, dynamic>> _tasksJson() => [
      {
        'id': 'task15',
        'int_id': 15,
        'task_id': 'T-15',
        'title': 'Grid Search Charlie-7',
        'task_type': 'Grid Search',
        'priority': 3,
        'status': 'Assigned',
        'location': 'Charlie-7 Grid',
        'task_teams': [
          {'team_id': 4, 'team_name': 'GT-4 Alpha'},
        ],
        'active_team_ids': [4],
      },
      {
        'id': 'task16',
        'int_id': 16,
        'task_id': 'T-16',
        'title': 'Trailhead containment',
        'task_type': 'Containment',
        'priority': 2,
        'status': 'Complete',
        'location': 'Trailhead C',
        'task_teams': [
          {'team_id': 7, 'team_name': 'GT-7 Bravo'},
        ],
        'active_team_ids': [7],
      },
    ];

SarAppApiClient _client({
  List<Map<String, dynamic>>? tasks,
  int statusCode = 200,
}) {
  final mock = MockClient((request) async {
    if (request.method == 'GET' &&
        request.url.path == '/api/incidents/$_incidentId/operations/tasks') {
      return http.Response(jsonEncode(tasks ?? _tasksJson()), statusCode);
    }
    return http.Response('not found', 404);
  });
  return SarAppApiClient(httpClient: mock, baseUrl: 'https://test.local');
}

Widget _wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('loads live task rows from the operations tasks endpoint', (tester) async {
    await tester.pumpWidget(_wrap(TaskListScreen(args: _args(), apiClient: _client())));
    await tester.pumpAndSettle();

    expect(find.textContaining('T-15'), findsOneWidget);
    expect(find.textContaining('Grid Search Charlie-7'), findsOneWidget);
    expect(find.text('HIGH'), findsOneWidget);
    expect(find.text('MY TEAM'), findsOneWidget);
  });

  testWidgets('my team filter only shows tasks assigned to the signed-in team', (tester) async {
    await tester.pumpWidget(_wrap(TaskListScreen(args: _args(), apiClient: _client())));
    await tester.pumpAndSettle();

    await tester.tap(find.text('My Team'));
    await tester.pumpAndSettle();

    expect(find.textContaining('T-15'), findsOneWidget);
    expect(find.textContaining('T-16'), findsNothing);
  });

  testWidgets('empty response shows an honest empty tasking state', (tester) async {
    await tester.pumpWidget(_wrap(TaskListScreen(
      args: _args(),
      apiClient: _client(tasks: const []),
    )));
    await tester.pumpAndSettle();

    expect(find.text('No tasks have been published for this incident.'), findsOneWidget);
    expect(find.textContaining('sample'), findsNothing);
  });

  testWidgets('server failure shows retryable error state', (tester) async {
    await tester.pumpWidget(_wrap(TaskListScreen(
      args: _args(),
      apiClient: _client(statusCode: 500),
    )));
    await tester.pumpAndSettle();

    expect(find.text('Unable to load tasks.'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });
}
