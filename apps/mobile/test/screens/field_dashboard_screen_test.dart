import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/screens/field_dashboard_screen.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';
import 'package:ics_mobile_app/widgets/assignment_reference_panel.dart';
import 'package:ics_mobile_app/widgets/narrative_feed.dart';
import 'package:ics_mobile_app/widgets/team_status_grid.dart';

const _incidentId = 'INC1';
const _teamName = 'GT-4 Alpha';

Map<String, dynamic> _headerJson() => {
      'incident_name': 'Missing Aircraft Search',
      'incident_number': 'OP2',
      'status': 'Active',
      'icp_location': 'Base Camp',
      'start_time': '2026-07-10T07:00:00Z',
    };

Map<String, dynamic> _teamJson({String status = 'On Scene', int? currentTaskId = 15}) => {
      'id': 't1',
      'int_id': 4,
      'name': _teamName,
      'status': status,
      'status_updated': '2026-07-10T09:41:00Z',
      'current_task_id': currentTaskId,
      'leader_name': 'John Smith',
    };

Map<String, dynamic> _taskJson() => {
      'id': 'task15',
      'int_id': 15,
      'task_id': 'T-15',
      'title': 'Grid Search Charlie-7',
      'task_type': 'Grid Search',
      'priority': 3,
      'status': 'Assigned',
      'location': 'Charlie-7 Grid / Access via Forest Road 212',
      'task_teams': [
        {'team_id': 4, 'team_name': _teamName, 'time_assigned': '2026-07-10T09:35:00Z'},
      ],
      'active_team_ids': [4],
    };

List<Map<String, dynamic>> _narrativesJson() => [
      {
        'id': 'n1',
        'task_id': 15,
        'timestamp': '2026-07-10T09:35:00Z',
        'narrative': 'Search Grid Charlie-7 for clues related to the missing aircraft.',
        'entered_by': 'OSC',
        'critical': 0,
      },
      {
        'id': 'n2',
        'task_id': 15,
        'timestamp': '2026-07-10T09:51:00Z',
        'narrative': 'Possible wreckage sighted 0.7 nm east of your position.',
        'entered_by': 'GT-2 (Radio)',
        'critical': 1,
      },
    ];

SarAppApiClient _buildClient({
  bool hasActiveTask = true,
  bool hasNarratives = true,
  void Function(Uri url, String body)? onPatch,
}) {
  final mock = MockClient((request) async {
    final path = request.url.path;
    if (request.method == 'GET' && path.endsWith('/header')) {
      return http.Response(jsonEncode(_headerJson()), 200);
    }
    if (request.method == 'GET' && path.endsWith('/op-periods')) {
      return http.Response(jsonEncode([1, 2]), 200);
    }
    if (request.method == 'GET' && path.endsWith('/operations/teams')) {
      return http.Response(
        jsonEncode([_teamJson(currentTaskId: hasActiveTask ? 15 : null)]),
        200,
      );
    }
    if (request.method == 'GET' && RegExp(r'/operations/teams/\d+$').hasMatch(path)) {
      return http.Response(
        jsonEncode(_teamJson(currentTaskId: hasActiveTask ? 15 : null)),
        200,
      );
    }
    if (request.method == 'PATCH' && RegExp(r'/operations/teams/\d+/status$').hasMatch(path)) {
      onPatch?.call(request.url, request.body);
      return http.Response(jsonEncode(_teamJson(status: 'En Route')), 200);
    }
    if (request.method == 'GET' && RegExp(r'/operations/tasks/\d+$').hasMatch(path)) {
      return http.Response(jsonEncode(_taskJson()), 200);
    }
    if (request.method == 'GET' && path.endsWith('/narratives')) {
      return http.Response(jsonEncode(hasNarratives ? _narrativesJson() : []), 200);
    }
    return http.Response('not found', 404);
  });
  return SarAppApiClient(httpClient: mock, baseUrl: 'https://test.local');
}

Widget _wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('renders task metadata and location for an active task', (tester) async {
    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: _buildClient(),
      )),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('T-15'), findsWidgets);
    expect(find.text('Grid Search Charlie-7'), findsOneWidget);
    expect(find.text('HIGH'), findsOneWidget); // priority 3 -> High, rendered uppercase in the chip
    expect(find.text('Charlie-7 Grid / Access via Forest Road 212'), findsOneWidget);
  });

  testWidgets('narrative entries render newest-first', (tester) async {
    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: _buildClient(),
      )),
    );
    await tester.pumpAndSettle();

    final newest = tester.getTopLeft(find.textContaining('Possible wreckage sighted')).dy;
    final oldest = tester.getTopLeft(find.textContaining('Search Grid Charlie-7 for clues')).dy;
    expect(newest, lessThan(oldest));
  });

  testWidgets('empty narrative state renders without fabricating entries', (tester) async {
    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: _buildClient(hasNarratives: false),
      )),
    );
    await tester.pumpAndSettle();

    expect(find.text('No narrative entries yet for this task.'), findsOneWidget);
  });

  testWidgets('narrative feed is framed so its scroll region is clearly defined', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: _buildClient(),
      )),
    );
    await tester.pumpAndSettle();

    final panel = tester.widget<Container>(find.byKey(const Key('dashboard_narrative_panel')));
    final decoration = panel.decoration as BoxDecoration;

    expect(find.descendant(of: find.byKey(const Key('dashboard_narrative_panel')), matching: find.byType(NarrativeFeed)), findsOneWidget);
    expect(decoration.border, isNotNull);
    expect(decoration.borderRadius, BorderRadius.circular(12));
  });

  testWidgets('no active task shows an honest empty state, not a fabricated task', (tester) async {
    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: _buildClient(hasActiveTask: false),
      )),
    );
    await tester.pumpAndSettle();

    expect(find.text('Your team has no active task assigned.'), findsOneWidget);
    expect(find.textContaining('T-15'), findsNothing);
  });

  testWidgets('current team status is visually selected in the status grid', (tester) async {
    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: _buildClient(),
      )),
    );
    await tester.pumpAndSettle();

    // The team's server-reported status "On Scene" should highlight the
    // matching button in the grid (bold/selected weight) and leave the
    // others unselected.
    final grid = find.byType(TeamStatusGrid);
    final onSceneText = tester.widget<Text>(
      find.descendant(of: grid, matching: find.text('On Scene')),
    );
    final availableText = tester.widget<Text>(
      find.descendant(of: grid, matching: find.text('Available')),
    );
    expect(onSceneText.style?.fontWeight, FontWeight.w800);
    expect(availableText.style?.fontWeight, FontWeight.w600);
  });

  testWidgets('tapping a status button calls the PATCH status endpoint', (tester) async {
    Uri? patchedUrl;
    String? patchedBody;
    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: _buildClient(onPatch: (url, body) {
          patchedUrl = url;
          patchedBody = body;
        }),
      )),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Available'));
    await tester.pumpAndSettle();

    expect(patchedUrl?.path, '/api/incidents/$_incidentId/operations/teams/4/status');
    expect(patchedBody, contains('"status_key":"available"'));
    expect(find.text('Status updated to Available'), findsOneWidget);
  });

  testWidgets('status update failure shows an error, never fails silently', (tester) async {
    final mock = MockClient((request) async {
      final path = request.url.path;
      if (request.method == 'GET' && path.endsWith('/header')) {
        return http.Response(jsonEncode(_headerJson()), 200);
      }
      if (request.method == 'GET' && path.endsWith('/op-periods')) {
        return http.Response(jsonEncode([1]), 200);
      }
      if (request.method == 'GET' && path.endsWith('/operations/teams')) {
        return http.Response(jsonEncode([_teamJson(currentTaskId: null)]), 200);
      }
      if (request.method == 'GET' && RegExp(r'/operations/teams/\d+$').hasMatch(path)) {
        return http.Response(jsonEncode(_teamJson(currentTaskId: null)), 200);
      }
      if (request.method == 'PATCH') {
        return http.Response('server error', 500);
      }
      return http.Response(jsonEncode([]), 200);
    });
    final apiClient = SarAppApiClient(httpClient: mock, baseUrl: 'https://test.local');

    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: apiClient,
      )),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Available'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Failed to update status'), findsOneWidget);
  });

  testWidgets('phone-width layout has no assignment reference panel', (tester) async {
    tester.view.physicalSize = const Size(400, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: _buildClient(),
      )),
    );
    await tester.pumpAndSettle();

    expect(find.byType(AssignmentReferencePanel), findsNothing);
  });

  testWidgets('wide/tablet layout shows the assignment reference panel', (tester) async {
    tester.view.physicalSize = const Size(1100, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      _wrap(FieldDashboardScreen(
        incidentId: _incidentId,
        incidentName: 'Missing Aircraft Search',
        teamId: 'anything',
        teamName: _teamName,
        session: const {'person_id': 'P100'},
        apiClient: _buildClient(),
      )),
    );
    await tester.pumpAndSettle();

    expect(find.byType(AssignmentReferencePanel), findsOneWidget);
    expect(find.text('No assignment reference attached.'), findsOneWidget);
  });
}
