import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/models/home_nav_args.dart';
import 'package:ics_mobile_app/screens/comms_plan_screen.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';

const _incidentId = 'INC1';

HomeNavArgs _args() => const HomeNavArgs(
      incidentId: _incidentId,
      incidentName: 'Missing Aircraft Search',
      teamId: '4',
      teamName: 'GT-4 Alpha',
      session: {'person_id': 'P100'},
    );

Map<String, dynamic> _planJson() => {
      'op_period_id': '2',
      'special_instructions': 'Use command net for priority traffic.',
      'phone_numbers': [
        {'label': 'COML', 'number': '555-0101'},
      ],
      'notes': 'Switch to backup repeater after 1800.',
    };

List<Map<String, dynamic>> _channelsJson() => [
      {
        'id': 1,
        'channel': 'TAC-1',
        'function': 'Command',
        'system': 'SAR VHF',
        'mode': 'FM',
        'band': 'VHF',
        'rx_freq': 155.55,
        'tx_freq': 155.55,
        'rx_tone': '100.0',
        'tx_tone': '100.0',
        'encryption': 'None',
        'assignment_division': 'Ops',
        'assignment_team': 'Field Teams',
        'priority': 'Primary',
        'remarks': 'Primary command net',
        'include_on_205': 1,
      },
      {
        'id': 2,
        'channel': 'ADMIN',
        'function': 'Admin',
        'mode': 'FM',
        'include_on_205': 0,
      },
    ];

SarAppApiClient _buildClient({
  bool failPlan = false,
  List<Map<String, dynamic>>? channels,
  Map<String, dynamic>? plan,
}) {
  final mock = MockClient((request) async {
    final path = request.url.path;
    if (request.method == 'GET' && path.endsWith('/op-periods')) {
      return http.Response(jsonEncode([1, 2]), 200);
    }
    if (request.method == 'GET' && path.endsWith('/channels-plan')) {
      return http.Response(jsonEncode(channels ?? _channelsJson()), 200);
    }
    if (request.method == 'GET' && path.endsWith('/communications-plan')) {
      if (failPlan) return http.Response('server error', 500);
      return http.Response(jsonEncode(plan ?? _planJson()), 200);
    }
    return http.Response('not found', 404);
  });
  return SarAppApiClient(httpClient: mock, baseUrl: 'https://test.local');
}

Widget _wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('renders live ICS 205 plan and included channel rows', (tester) async {
    await tester.pumpWidget(
      _wrap(CommsPlanScreen(args: _args(), apiClient: _buildClient())),
    );
    await tester.pumpAndSettle();

    expect(find.text('Operational period 2'), findsOneWidget);
    expect(find.text('Use command net for priority traffic.'), findsOneWidget);
    expect(find.text('TAC-1'), findsOneWidget);
    expect(find.text('Primary command net'), findsOneWidget);
    expect(find.text('ADMIN'), findsNothing);
    expect(find.textContaining('Preview data'), findsNothing);
    expect(find.text('COML'), findsNothing);
    expect(find.text('555-0101'), findsNothing);
    expect(find.text('SAR VHF'), findsNothing);
  });

  testWidgets('renders empty state when no plan data exists', (tester) async {
    await tester.pumpWidget(
      _wrap(CommsPlanScreen(
        args: _args(),
        apiClient: _buildClient(channels: [], plan: {'phone_numbers': []}),
      )),
    );
    await tester.pumpAndSettle();

    expect(find.text('No ICS 205 has been published for this incident.'), findsOneWidget);
  });

  testWidgets('renders retry state when the API request fails', (tester) async {
    await tester.pumpWidget(
      _wrap(CommsPlanScreen(args: _args(), apiClient: _buildClient(failPlan: true))),
    );
    await tester.pumpAndSettle();

    expect(find.text('Unable to load the communications plan.'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Retry'), findsOneWidget);
  });
}
