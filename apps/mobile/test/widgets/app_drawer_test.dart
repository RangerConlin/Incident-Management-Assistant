import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/home_nav_args.dart';
import 'package:ics_mobile_app/screens/main_menu_screen.dart';
import 'package:ics_mobile_app/services/server_connection_store.dart';
import 'package:ics_mobile_app/services/session_store.dart';
import 'package:ics_mobile_app/widgets/app_drawer.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _args = HomeNavArgs(
  incidentId: 'INC-1',
  incidentName: 'Search Exercise',
  teamId: 'TEAM-1',
  teamName: 'Ground Team 1',
  session: {'person_id': 'P100'},
);

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await ServerConnectionStore.initialize();
    await SessionStore.save(
      incidentId: _args.incidentId,
      incidentName: _args.incidentName,
      teamId: _args.teamId,
      teamName: _args.teamName,
      session: _args.session,
    );
  });

  Future<void> openDrawerAndTap(WidgetTester tester, String label) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          appBar: AppBar(),
          drawer: const AppDrawer(args: _args),
        ),
      ),
    );
    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.drag(find.byType(ListView), const Offset(0, -600));
    await tester.pumpAndSettle();
    await tester.tap(find.text(label));
    await tester.pumpAndSettle();
  }

  testWidgets('switch incident clears the session and opens the main menu', (
    tester,
  ) async {
    await openDrawerAndTap(tester, 'Switch Incident');

    expect(find.byType(MainMenuScreen), findsOneWidget);
    expect(await SessionStore.load(), isNull);
  });

  testWidgets('log out clears the session and opens the main menu', (
    tester,
  ) async {
    await openDrawerAndTap(tester, 'Log Out');

    expect(find.byType(MainMenuScreen), findsOneWidget);
    expect(await SessionStore.load(), isNull);
  });
}
