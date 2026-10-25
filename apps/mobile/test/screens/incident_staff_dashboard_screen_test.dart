import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/screens/incident_staff_dashboard_screen.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';

const _incidentId = 'INC1';

Map<String, dynamic> _mobileContextJson({
  List<Map<String, dynamic>> staffAssignments = const [],
  Map<String, dynamic>? team,
}) => {
  'person': {'person_record': 100, 'name': 'Jordan Smith'},
  'resource_status': {'status': 'Checked In'},
  'team': team,
  'staff_assignments': staffAssignments,
};

Map<String, dynamic> _teamJson({
  int intId = 4,
  String name = 'Ground Team 2',
  String status = 'En Route',
}) => {
  'id': 't$intId',
  'int_id': intId,
  'name': name,
  'status': status,
  'current_task_id': null,
};

SarAppApiClient _buildClient({
  List<Map<String, dynamic>> staffAssignments = const [],
  Map<String, dynamic>? team,
  List<Map<String, dynamic>> teams = const [],
  bool offline = false,
}) {
  final mock = MockClient((request) async {
    if (offline) return http.Response('server error', 500);
    final path = request.url.path;
    if (path.endsWith('/op-periods')) {
      return http.Response(jsonEncode([3]), 200);
    }
    if (path.contains('/mobile/context/')) {
      return http.Response(
        jsonEncode(_mobileContextJson(staffAssignments: staffAssignments, team: team)),
        200,
      );
    }
    if (path.endsWith('/operations/teams')) {
      return http.Response(jsonEncode(teams), 200);
    }
    if (path.endsWith('/operations/tasks')) {
      return http.Response(jsonEncode([]), 200);
    }
    if (path.endsWith('/checkin/roster')) {
      return http.Response(jsonEncode([]), 200);
    }
    if (path.endsWith('/safety/hazards')) {
      return http.Response(jsonEncode([]), 200);
    }
    if (path.endsWith('/objectives')) {
      return http.Response(jsonEncode([]), 200);
    }
    if (path.endsWith('/narratives')) {
      return http.Response(jsonEncode([]), 200);
    }
    return http.Response('not found', 404);
  });
  return SarAppApiClient(httpClient: mock, baseUrl: 'https://test.local');
}

Widget _wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('new entrant with no assignment and no team shows no assignment card or switch icon', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        IncidentStaffDashboardScreen(
          incidentId: _incidentId,
          incidentName: 'Pine Ridge SAR',
          session: const {'person_id': 'P100', 'person_record': 100},
          apiClient: _buildClient(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('YOUR ASSIGNMENT'), findsNothing);
    expect(find.byIcon(Icons.swap_horiz), findsNothing);
    expect(find.text('TEAMS ACTIVE'), findsOneWidget);
    expect(find.text('No objectives recorded yet.'), findsOneWidget);
  });

  testWidgets('staff position with no team shows the assignment card, no switch icon', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        IncidentStaffDashboardScreen(
          incidentId: _incidentId,
          incidentName: 'Pine Ridge SAR',
          session: const {'person_id': 'P100', 'person_record': 100},
          apiClient: _buildClient(
            staffAssignments: [
              {
                'position_id': 17,
                'title': 'Communications Unit Leader',
                'classification': 'Communications Unit',
                'assignment_type': 'primary',
                'start_time': '2026-10-21T13:30:00Z',
              },
            ],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('YOUR ASSIGNMENT'), findsOneWidget);
    expect(find.text('Communications Unit Leader'), findsOneWidget);
    expect(find.byIcon(Icons.swap_horiz), findsNothing);
    expect(find.textContaining('Also on'), findsNothing);
  });

  testWidgets('staff position plus a team shows the switch icon and the team banner', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        IncidentStaffDashboardScreen(
          incidentId: _incidentId,
          incidentName: 'Pine Ridge SAR',
          session: const {'person_id': 'P100', 'person_record': 100},
          apiClient: _buildClient(
            staffAssignments: [
              {
                'position_id': 17,
                'title': 'Communications Unit Leader',
                'classification': 'Communications Unit',
                'assignment_type': 'primary',
                'start_time': '2026-10-21T13:30:00Z',
              },
            ],
            team: {
              'team_id': 4,
              'team_name': 'Ground Team 2',
              'team_role': 'Ground Search',
              'is_leader': false,
            },
            teams: [_teamJson()],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.swap_horiz), findsOneWidget);
    expect(find.textContaining('Also on Ground Team 2'), findsOneWidget);
    expect(find.text('YOU'), findsOneWidget);
  });

  testWidgets('a fetch failure shows the offline state, not stale or fabricated content', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        IncidentStaffDashboardScreen(
          incidentId: _incidentId,
          incidentName: 'Pine Ridge SAR',
          session: const {'person_id': 'P100', 'person_record': 100},
          apiClient: _buildClient(offline: true),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text("You're offline"), findsOneWidget);
    expect(find.text('TEAMS ACTIVE'), findsNothing);
    expect(find.text('YOUR ASSIGNMENT'), findsNothing);
  });
}
