import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/screens/connections_screen.dart';
import 'package:ics_mobile_app/screens/profile_screen.dart';
import 'package:ics_mobile_app/services/local_profile_store.dart';
import 'package:ics_mobile_app/services/server_connection_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await ServerConnectionStore.initialize();
  });

  testWidgets('profile requires ID and both names, then saves locally', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(const MaterialApp(home: ProfileScreen()));

    await tester.tap(find.text('Save profile'));
    await tester.pumpAndSettle();
    expect(
      find.text('Person ID, first name and last name are required.'),
      findsOneWidget,
    );
    expect(await LocalProfileStore.load(), isNull);

    await tester.enterText(
      find.widgetWithText(TextField, 'Person ID *'),
      ' 405021 ',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'First name *'),
      'Jane',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Last name *'),
      'Doe',
    );
    // The organization picker defaults to "Other" with no prior value, which
    // shows this free-text field.
    await tester.enterText(
      find.widgetWithText(TextField, 'Organization (not listed above)'),
      'CAP',
    );
    await tester.enterText(find.widgetWithText(TextField, 'Radio ID'), 'R-7');
    await tester.tap(find.text('Save profile'));
    await tester.pumpAndSettle();

    final saved = await LocalProfileStore.load();
    expect(saved?.personId, '405021');
    expect(saved?.fullName, 'Jane Doe');
    expect(saved?.organization, 'CAP');
    expect(saved?.radioId, 'R-7');
  });

  testWidgets('editing prefills the existing profile', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: ProfileScreen(
          existing: LocalProfile(
            personId: '1',
            firstName: 'A',
            lastName: 'B',
            phone: '555',
          ),
        ),
      ),
    );

    expect(find.text('Edit profile'), findsOneWidget);
    expect(find.widgetWithText(TextField, '555'), findsOneWidget);
  });

  testWidgets('a connect code is validated, saved, and made active', (
    tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: ConnectionsScreen()));

    await tester.enterText(find.widgetWithText(TextField, 'Connect code'), 'x');
    await tester.tap(find.text('Add and use'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Enter the connect code'), findsOneWidget);
    expect(await ServerConnectionStore.loadAll(), isEmpty);

    await tester.enterText(
      find.widgetWithText(TextField, 'Connect code'),
      ' abcd-1234 ',
    );
    await tester.tap(find.text('Add and use'));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(ListTile, 'ABCD-1234'), findsOneWidget);
    expect(ServerConnectionStore.active?.code, 'ABCD-1234');

    await tester.tap(find.byTooltip('Forget ABCD-1234'));
    await tester.pumpAndSettle();
    expect(ServerConnectionStore.active, isNull);
    expect(await ServerConnectionStore.loadAll(), isEmpty);
  });

  test('connection input normalization', () {
    expect(ServerConnection.normalizeCode(' ab-12 '), 'AB-12');
    expect(ServerConnection.normalizeCode('a'), isNull);
    expect(ServerConnection.normalizeCode('bad code!'), isNull);
    expect(
      ServerConnection.normalizeRouterUrl('https://r.example/'),
      'https://r.example',
    );
    expect(ServerConnection.normalizeRouterUrl('not a url'), isNull);
    expect(ServerConnection.normalizeRouterUrl(''), isNotNull);
  });

  testWidgets('editing locks the Person ID and can remove the profile', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    const existing = LocalProfile(
      personId: '405021',
      firstName: 'Jane',
      lastName: 'Doe',
    );
    await LocalProfileStore.save(existing);
    await tester.pumpWidget(
      const MaterialApp(home: ProfileScreen(existing: existing)),
    );

    final idField = tester.widget<TextField>(
      find.widgetWithText(TextField, '405021'),
    );
    expect(idField.enabled, isFalse);

    await tester.tap(find.text('Remove profile from this device'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Remove'));
    await tester.pumpAndSettle();

    expect(await LocalProfileStore.load(), isNull);
  });
}
